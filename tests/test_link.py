import os
import tempfile
import unittest
from unittest import mock

from amiberry_remote.link import AmiberryError, Link, socket_path
from tests.fake_amiberry import FakeAmiberry


class LinkTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeAmiberry().start()
        self.addCleanup(self.fake.__exit__)
        self.link = Link(self.fake.path)

    def test_ok_reply_gives_its_fields(self):
        self.assertEqual(self.link.send("PING"), ["PONG"])
        self.fake.put_long(4, 0x200830)
        self.assertEqual(self.link.send("READ_MEM", 4, 4), [str(0x200830)])
        self.assertEqual(self.fake.commands(), ["PING", "READ_MEM\t4\t4"])

    def test_error_reply_names_the_command(self):
        self.fake.replies["SEND_KEY"] = "ERROR\tinvalid key code"
        with self.assertRaises(AmiberryError) as e:
            self.link.send("SEND_KEY", 999, 1)
        self.assertIn("SEND_KEY 999 1", str(e.exception))
        self.assertIn("invalid key code", str(e.exception))

    def test_ping(self):
        self.assertTrue(self.link.ping())


class NotRunningTest(unittest.TestCase):
    def test_missing_socket(self):
        with tempfile.TemporaryDirectory() as d:
            link = Link(os.path.join(d, "amiberry.sock"))
            with self.assertRaises(AmiberryError) as e:
                link.send("PING")
            self.assertIn("Amiberry is not running", str(e.exception))
            self.assertFalse(link.ping())

    def test_quit_removes_the_socket(self):
        fake = FakeAmiberry().start()
        link = Link(fake.path)
        link.send("QUIT")
        fake.thread.join(2)
        with self.assertRaises(AmiberryError) as e:
            link.send("PING")
        self.assertIn("Amiberry is not running", str(e.exception))
        fake.__exit__()


class SocketPathTest(unittest.TestCase):
    def test_environment(self):
        with mock.patch.dict(os.environ, {"AMIBERRY_SOCKET": "/x/a.sock"}):
            self.assertEqual(socket_path(), "/x/a.sock")
        env = {k: v for k, v in os.environ.items() if k != "AMIBERRY_SOCKET"}
        env["XDG_RUNTIME_DIR"] = "/run/user/77"
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(socket_path(), "/run/user/77/amiberry.sock")


if __name__ == "__main__":
    unittest.main()
