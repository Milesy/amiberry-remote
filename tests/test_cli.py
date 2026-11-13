import io
import os
import sys
import tempfile
import unittest
import warnings
from unittest import mock

from PIL import Image

from amiberry_remote.cli import main
from amiberry_remote.session import Amiga
from tests.fake_amiberry import FakeAmiberry
from tests.test_hunks import LENGTHS, write_hunk_file
from tests.test_screen import picture
from tests.test_session import executable

HERE = os.path.dirname(os.path.abspath(__file__))


class CliTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeAmiberry().start()
        self.addCleanup(self.fake.__exit__)
        self.fake.boot_workbench()
        self.env = mock.patch.dict(os.environ, {"AMIBERRY_SOCKET": self.fake.path})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        status = main(list(argv), out, err)
        return status, out.getvalue(), err.getvalue()

    def ok(self, *argv):
        status, out, err = self.cli(*argv)
        self.assertEqual((status, err), (0, ""), argv)
        return out

    def test_peek_numbers(self):
        expected = f"${self.fake.exec_base:08X}\n"
        for address in ("$4", "0x4", "4"):
            self.assertEqual(self.ok("peek", address, "l"), expected)
        self.assertEqual(self.ok("peek", "$4"), expected)
        self.fake.put_bytes(0x100, b"\x12\x34Hello, Amiga!\x00\xff\x01")
        self.assertEqual(self.ok("peek", "$100", "b"), "$12\n")
        self.assertEqual(self.ok("peek", "256", "w"), "$1234\n")
        self.assertEqual(self.ok("peek", "$100", "18"),
                         "$00000100: 12 34 48 65 6c 6c 6f 2c 20 41 6d 69 67 61 21 00  .4Hello, Amiga!.\n"
                         "$00000110: ff 01                                            ..\n")

    def test_poke(self):
        self.ok("poke", "$200", "w", "0x4E71")
        self.ok("poke", "$204", "l", "-1")
        self.ok("poke", "$208", "b", "$7f")
        self.assertEqual(bytes(self.fake.memory[0x200:0x209]), bytes.fromhex("4e71 0000 ffffffff 7f"))

    def test_library_and_screen(self):
        self.assertEqual(self.ok("library", "intuition.library"),
                         f"${self.fake.intuition_base:08X} version 40\n")
        out = self.ok("screen")
        self.assertIn("640 x 256 at 0, 0, depth 2, Workbench, 'Workbench Screen'", out)

    def test_hunks(self):
        _, segments = self.fake.add_detached("OctaMED", LENGTHS[1:])
        path = os.path.join(self.dir.name, "OctaMED.patched")
        write_hunk_file(path, LENGTHS)
        lines = self.ok("hunks", path).splitlines()
        self.assertEqual(lines[0].split(), ["0", "not", "loaded", "$33C"])
        self.assertEqual(lines[1].split(), ["1", f"${segments[0][0]:08X}", "$128C"])
        self.assertEqual(len(lines), 4)

    def test_keys_and_typing(self):
        self.fake.add_window(self.fake.workbench_screen, "AmigaShell", 0, 0, 640, 130)
        self.ok("key", "Help", "Ctrl-F2")
        self.ok("type", "dir\\n")
        self.assertEqual(self.fake.key_events()[:2], [(0x5F, True), (0x5F, False)])
        self.assertEqual(self.fake.lines[-1][1], "dir")

    def test_pointer_click_drag(self):
        self.fake.put_mouse(10, 20)
        self.assertEqual(self.ok("pointer"), "10 20\n")
        self.ok("click", "330", "48")
        self.assertEqual(self.fake.button_events[-2:], [(1, (330, 48)), (0, (330, 48))])
        self.ok("click", "$10", "$10", "right")
        self.assertEqual(self.fake.button_events[-2][0], 2)
        self.ok("drag", "100", "120", "110", "120")
        self.assertEqual(self.fake.button_events[-2:], [(1, (100, 120)), (0, (110, 120))])

    def test_shot(self):
        self.fake.show_pointer = False
        self.fake.draw(self.fake.workbench_screen, picture(640, 256, 2, seed=4))
        path = os.path.join(self.dir.name, "now.png")
        self.assertEqual(self.ok("shot", path), "640 x 256\n")
        with Image.open(path) as image:
            self.assertEqual(image.size, (640, 256))

    def test_run(self):
        self.ok("run", "cd PC:OctaMED", "OctaMED.patched")
        self.assertEqual(self.fake.shell_lines(), ["cd PC:OctaMED", "OctaMED.patched"])

    def test_send(self):
        self.assertEqual(self.ok("send", "PING"), "OK\tPONG\n")
        status, out, err = self.cli("send", "FROB")
        self.assertEqual((status, out), (1, ""))
        self.assertEqual(err.count("\n"), 1)

    def test_quit(self):
        self.assertEqual(self.ok("quit"), "Amiberry has quit\n")
        status, out, err = self.cli("pointer")
        self.assertEqual(status, 1)

    def test_start(self):
        self.fake.stop()
        socket = os.path.join(self.dir.name, "amiberry.sock")
        program = executable(os.path.join(self.dir.name, "amiberry"),
                             f"#!/bin/sh\nexec '{sys.executable}' '{HERE}/fake_amiberry.py' \"$@\"\n")
        config = os.path.join(self.dir.name, "A1200.uae")
        open(config, "w").close()
        with mock.patch.dict(os.environ, {"AMIBERRY": program, "AMIBERRY_SOCKET": socket}), \
                mock.patch.multiple(Amiga, poll=0.02, settle=0.02):
            with warnings.catch_warnings():
                # The command leaves Amiberry running as it exits, as it should.
                warnings.simplefilter("ignore", ResourceWarning)
                self.assertEqual(self.ok("start", config), "Workbench is up\n")
            self.assertEqual(self.ok("quit"), "Amiberry has quit\n")

    def test_failures_are_one_line(self):
        with mock.patch.dict(os.environ, {"AMIBERRY_SOCKET": os.path.join(self.dir.name, "none")}):
            status, out, err = self.cli("pointer")
        self.assertEqual((status, out), (1, ""))
        self.assertTrue(err.startswith("amiberry-remote: Amiberry is not running"))
        self.assertEqual(err.count("\n"), 1)
        status, out, err = self.cli("key", "Hlep")
        self.assertEqual((status, err.count("\n")), (1, 1))
        self.assertIn("'Hlep'", err)

    def test_usage_errors_are_one_line(self):
        with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            with self.assertRaises(SystemExit) as e:
                main(["peek", "four"])
        self.assertEqual(e.exception.code, 2)
        self.assertEqual(err.getvalue().count("\n"), 1)
        self.assertIn("'four' isn't a number", err.getvalue())


if __name__ == "__main__":
    unittest.main()
