import unittest

from amiberry_remote.link import AmiberryError, Link
from amiberry_remote.memory import Memory
from tests.fake_amiberry import FakeAmiberry


class MemoryTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeAmiberry().start()
        self.addCleanup(self.fake.__exit__)
        self.fake.boot_workbench()
        self.memory = Memory(Link(self.fake.path))

    def test_big_endian(self):
        self.fake.put_bytes(0x100, bytes([0x12, 0x34, 0x56, 0x78]))
        self.assertEqual(self.memory.read_long(0x100), 0x12345678)
        self.assertEqual(self.memory.read_word(0x102), 0x5678)
        self.assertEqual(self.memory.read_byte(0x101), 0x34)
        self.memory.write(0x200, 4, 0xCAFEBABE)
        self.assertEqual(bytes(self.fake.memory[0x200:0x204]), bytes([0xCA, 0xFE, 0xBA, 0xBE]))
        self.memory.write(0x204, 2, -2)
        self.assertEqual(bytes(self.fake.memory[0x204:0x206]), bytes([0xFF, 0xFE]))
        self.assertEqual(self.memory.read_signed_word(0x204), -2)

    def test_execbase(self):
        self.assertEqual(self.memory.read_long(4), self.fake.exec_base)
        self.assertEqual(self.memory.exec_base(), self.fake.exec_base)

    def test_execbase_not_set(self):
        self.fake.put_long(4, 0xF800D2)        # during reset: the ROM's start address
        with self.assertRaises(AmiberryError) as e:
            self.memory.exec_base()
        self.assertIn("ExecBase", str(e.exception))

    def test_odd_address_sends_nothing(self):
        for size in (2, 4):
            with self.assertRaises(AmiberryError) as e:
                self.memory.read(5, size)
            self.assertIn("odd address $5", str(e.exception))
            with self.assertRaises(AmiberryError):
                self.memory.write(5, size, 0)
        self.assertEqual(self.fake.commands(), [])
        self.assertEqual(self.memory.read(5, 1), 0)

    def test_bad_values_send_nothing(self):
        for size, value in ((1, 256), (2, 0x10000), (4, 1 << 32), (1, -129)):
            with self.assertRaises(AmiberryError):
                self.memory.write(0x100, size, value)
        with self.assertRaises(AmiberryError):
            self.memory.read(0x100, 3)
        self.assertEqual(self.fake.commands(), [])

    def test_block_in_order(self):
        data = bytes((i * 7 + 3) & 0xFF for i in range(1040))
        self.fake.put_bytes(0x8000, data)
        self.assertEqual(self.memory.read_block(0x8000, 1040), data)
        self.assertEqual(len(self.fake.commands("READ_MEM")), 260)
        self.assertEqual(self.memory.read_block(0x8001, 6), data[1:7])   # odd start and end

    def test_string(self):
        addr = self.fake.put_string("Copyright © 1985")
        self.assertEqual(self.memory.read_string(addr), "Copyright © 1985")
        self.assertEqual(self.memory.read_string(addr + 1), "opyright © 1985")
        self.assertIsNone(self.memory.read_string(0))

    def test_library(self):
        lib = self.memory.library("intuition.library")
        self.assertEqual(lib.address, self.fake.intuition_base)
        self.assertEqual(lib.version, 40)
        names = [l.name for l in self.memory.libraries()]
        self.assertEqual(names, ["exec.library", "graphics.library", "intuition.library", "dos.library"])

    def test_unknown_library(self):
        with self.assertRaises(AmiberryError) as e:
            self.memory.library("intution.library")
        self.assertIn("'intution.library'", str(e.exception))

    def test_front_screen(self):
        self.fake.add_screen(640, 256, 3, "OctaMED Professional")
        screen = self.memory.front_screen()
        self.assertEqual((screen.width, screen.height, screen.title), (640, 256, "OctaMED Professional"))
        self.assertEqual((screen.left, screen.top), (0, 0))
        self.assertFalse(screen.is_workbench)
        self.assertEqual((screen.bitmap.depth, screen.bitmap.bytes_per_row, screen.bitmap.rows), (3, 80, 256))

    def test_workbench_screen(self):
        screen = self.memory.front_screen()
        self.assertTrue(screen.is_workbench)
        self.assertEqual(screen.bitmap.bytes_per_row, 160)     # interleaved, 2 planes
        self.assertEqual(screen.bitmap.planes[1] - screen.bitmap.planes[0], 80)

    def test_active_window(self):
        window = self.memory.active_window()
        self.assertEqual(window.address, self.fake.backdrop)
        self.assertIsNone(window.title)
        self.assertEqual(window.screen, self.fake.workbench_screen)
        shell = self.fake.add_window(self.fake.workbench_screen, "AmigaShell", 0, 0, 640, 130)
        window = self.memory.active_window()
        self.assertEqual((window.address, window.title, window.width), (shell, "AmigaShell", 640))

    def test_tasks_listed_once(self):
        task = self.fake.workbench_task
        self.fake.set_this_task(task)       # running, and still in the wait list: read mid-move
        tasks = self.memory.tasks()
        self.assertEqual(tasks.count(task), 1)
        self.assertEqual(sorted(self.memory.task_name(t) for t in tasks), ["Workbench", "input.device"])


if __name__ == "__main__":
    unittest.main()
