import os
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from amiberry_remote import session
from amiberry_remote.link import AmiberryError, Link, NotRunning
from amiberry_remote.session import Amiga, find_amiberry
from tests.fake_amiberry import FakeAmiberry
from tests.test_pointer import Clock

HERE = os.path.dirname(os.path.abspath(__file__))


def quick(amiga):
    """No waiting between keys, moves and clicks; short waits for windows and Workbench."""
    clock = Clock()
    amiga.keyboard.sleep = clock.sleep
    amiga.mouse.sleep, amiga.mouse.clock = clock.sleep, clock
    amiga.poll = amiga.settle = 0.02
    amiga.window_limit = 0.2
    return amiga


def executable(path, text="#!/bin/sh\n"):
    with open(path, "w") as f:
        f.write(text)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    return path


class ConnectTest(unittest.TestCase):
    def test_uses_a_running_amiberry_without_resetting_it(self):
        with FakeAmiberry() as fake:
            fake.boot_workbench()
            amiga = Amiga.connect(fake.path)
            self.assertEqual(amiga.library("intuition.library").version, 40)
            self.assertNotIn("RESET", [c.split("\t")[0] for c in fake.commands()])

    def test_not_running(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(NotRunning) as e:
                Amiga.connect(os.path.join(d, "amiberry.sock"))
            self.assertIn("Amiberry is not running", str(e.exception))


class FindAmiberryTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.bin = os.path.join(self.dir.name, "bin")
        os.mkdir(self.bin)
        self.env = {k: v for k, v in os.environ.items() if k != "AMIBERRY"}
        self.env["PATH"] = self.bin
        self.appimage = os.path.join(self.dir.name, "Amiberry.AppImage")

    def find(self, **env):
        with mock.patch.dict(os.environ, dict(self.env, **env), clear=True), \
                mock.patch.object(session, "APPIMAGE", self.appimage):
            return find_amiberry()

    def test_three_places_in_order(self):
        mine = executable(os.path.join(self.dir.name, "my-amiberry"))
        on_path = executable(os.path.join(self.bin, "amiberry"))
        executable(self.appimage)
        self.assertEqual(self.find(AMIBERRY=mine), mine)
        self.assertEqual(self.find(), on_path)
        os.unlink(on_path)
        self.assertEqual(self.find(), self.appimage)

    def test_none_found(self):
        with self.assertRaises(AmiberryError) as e:
            self.find(AMIBERRY="/nowhere/amiberry")
        message = str(e.exception)
        for place in ("$AMIBERRY (/nowhere/amiberry)", "amiberry on the PATH", self.appimage):
            self.assertIn(place, message)


class StartTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.config = os.path.join(self.dir.name, "A1200-OctaMED.uae")
        with open(self.config, "w") as f:
            f.write("use_gui=yes\n")
        self.socket = os.path.join(self.dir.name, "amiberry.sock")

    def test_config_missing_starts_nothing(self):
        with mock.patch.object(subprocess, "Popen") as popen:
            with self.assertRaises(AmiberryError) as e:
                Amiga.start(os.path.join(self.dir.name, "missing.uae"), socket=self.socket)
        self.assertIn("missing.uae", str(e.exception))
        popen.assert_not_called()

    def test_starts_the_program_with_the_config(self):
        program = executable(os.path.join(self.dir.name, "amiberry"),
                             f"#!/bin/sh\nexec '{sys.executable}' '{HERE}/fake_amiberry.py' \"$@\"\n")
        args = os.path.join(self.dir.name, "args")
        env = dict(AMIBERRY=program, AMIBERRY_SOCKET=self.socket, FAKE_AMIBERRY_ARGS=args)
        with mock.patch.dict(os.environ, env), mock.patch.multiple(Amiga, poll=0.02, settle=0.02):
            with open(self.config, "rb") as f:
                before = f.read()
            amiga = Amiga.start(self.config, socket=self.socket)
            try:
                with open(args) as f:
                    self.assertEqual(f.read().split("\n"), ["--config", self.config, "-G"])
                self.assertTrue(amiga.front_screen().is_workbench)
            finally:
                amiga.quit()
        self.assertFalse(Link(self.socket).ping())
        self.assertIsNotNone(amiga.process.poll())
        with open(self.config, "rb") as f:
            self.assertEqual(f.read(), before)

    def test_uses_one_already_running(self):
        with FakeAmiberry(self.socket) as fake, mock.patch.object(subprocess, "Popen") as popen, \
                mock.patch.multiple(Amiga, poll=0.02, settle=0.02):
            fake.boot_workbench()
            Amiga.start(self.config, socket=self.socket)
        popen.assert_not_called()


class WorkbenchTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeAmiberry().start()
        self.addCleanup(self.fake.__exit__)
        self.fake.put_long(4, 0xF800D2)          # resetting: the ROM's start address at 4
        self.amiga = quick(Amiga(Link(self.fake.path)))
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.amiga.screenshots.save_dir = self.dir.name

    def test_returns_once_workbench_is_up(self):
        booted = []
        def boot():
            self.fake.boot_workbench()
            booted.append(time.monotonic())
        timer = threading.Timer(0.3, boot)
        timer.start()
        self.addCleanup(timer.cancel)
        self.amiga.wait_for_workbench(timeout=10)
        self.assertTrue(booted)
        self.assertLess(time.monotonic() - booted[0], 0.5)

    def test_times_out_with_a_screenshot(self):
        self.fake.boot_exec()
        self.fake.boot_intuition()                # no Workbench process yet
        with self.assertRaises(AmiberryError) as e:
            self.amiga.wait_for_workbench(timeout=0.3)
        message = str(e.exception)
        self.assertIn("within 0.3 s: still waiting for the Workbench process", message)
        path = message.split("(screenshot ")[1].rstrip(")")
        self.assertTrue(os.path.isfile(path))


class RunTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeAmiberry().start()
        self.addCleanup(self.fake.__exit__)
        self.fake.boot_workbench()
        self.fake.put_mouse(100, 100)
        self.amiga = quick(Amiga(Link(self.fake.path)))

    def test_typed_into_the_new_shell(self):
        self.amiga.run("cd PC:OctaMED", "OctaMED.patched")
        self.assertEqual(self.fake.shell_lines(), ["cd PC:OctaMED", "OctaMED.patched"])
        self.assertEqual([l for w, l in self.fake.lines if w not in self.fake.shells], ["newshell"])
        self.assertEqual(self.fake.active(), self.fake.shells[0])

    def test_workbench_window_given_the_keyboard_first(self):
        # An old Shell has the keyboard and covers the top of the screen, title bar included.
        old = self.fake.add_window(self.fake.workbench_screen, "AmigaShell", 0, 0, 640, 130)
        self.amiga.run("dir")
        self.assertEqual(self.fake.shell_lines(), ["dir"])
        clicked = [pos for buttons, pos in self.fake.button_events if buttons == 1][0]
        self.assertGreaterEqual(clicked[1], 130)                 # below the old Shell
        self.assertNotIn(old, [w for w, _ in self.fake.lines])

    def test_requester_cleared_of_the_last_command(self):
        self.fake.execute_text = "newshell"
        self.amiga.run("dir")
        self.assertEqual(self.fake.shell_lines(), ["dir"])
        self.amiga.run("list")
        self.assertEqual(self.fake.shell_lines(), ["dir", "list"])
        self.assertEqual(len(self.fake.shells), 2)

    def test_new_shell_clicked_if_it_has_no_keyboard(self):
        self.fake.shell_activates = False
        self.amiga.run("dir")
        self.assertEqual(self.fake.shell_lines(), ["dir"])

    def test_not_workbench_in_front(self):
        self.fake.add_screen(640, 256, 3, "OctaMED")
        with self.assertRaises(AmiberryError) as e:
            self.amiga.run("dir")
        self.assertIn("'OctaMED' is in front", str(e.exception))
        self.assertEqual(self.fake.commands("SEND_KEY"), [])


class PauseTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeAmiberry().start()
        self.addCleanup(self.fake.__exit__)
        self.amiga = Amiga(Link(self.fake.path))

    def test_pause_and_resume(self):
        self.amiga.pause()
        self.assertTrue(self.fake.paused)
        self.amiga.resume()
        self.assertFalse(self.fake.paused)
        self.assertEqual(self.fake.commands(), ["PAUSE", "RESUME"])

    def test_paused_block_resumes_whatever_happens(self):
        with self.amiga.paused():
            self.assertTrue(self.fake.paused)
        self.assertFalse(self.fake.paused)
        with self.assertRaises(KeyError):
            with self.amiga.paused():
                raise KeyError("in the block")
        self.assertFalse(self.fake.paused)
        self.assertEqual(self.fake.commands(), ["PAUSE", "RESUME", "PAUSE", "RESUME"])

    def test_refused(self):
        self.fake.replies["PAUSE"] = "ERROR\tbusy"
        with self.assertRaises(AmiberryError) as e:
            self.amiga.pause()
        self.assertIn("PAUSE", str(e.exception))


class RawShotTest(unittest.TestCase):
    def test_amiberrys_own_screenshot(self):
        with FakeAmiberry() as fake, tempfile.TemporaryDirectory() as d:
            fake.boot_workbench()
            amiga = Amiga(Link(fake.path))
            path = os.path.join(d, "raw.png")
            picture = amiga.raw_shot(path)
            self.assertEqual(picture.size, (756, 576))
            self.assertEqual(fake.shots, [path])
            self.assertEqual(amiga.raw_shot().size, (756, 576))


class QuitTest(unittest.TestCase):
    def test_waits_until_the_socket_is_gone(self):
        with FakeAmiberry() as fake:
            fake.quit_delay = 0.3
            amiga = quick(Amiga(Link(fake.path)))
            start = time.monotonic()
            amiga.quit()
            self.assertGreaterEqual(time.monotonic() - start, 0.25)
            self.assertFalse(amiga.link.ping())


if __name__ == "__main__":
    unittest.main()
