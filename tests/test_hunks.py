import os
import struct
import tempfile
import unittest

from amiberry_remote.link import AmiberryError, Link
from amiberry_remote.memory import Hunk, Memory, hunk_sizes
from tests.fake_amiberry import FakeAmiberry

LENGTHS = [828, 4748, 60, 66372]


def write_hunk_file(path, lengths, chip=()):
    """A hunk file's header (the rest isn't read): lengths in bytes, some in chip memory."""
    longs = [0x3F3, 0, 4 * 0 + len(lengths), 0, len(lengths) - 1]
    for n, length in enumerate(lengths):
        longs.append(length // 4 | (1 << 30 if n in chip else 0))
    longs += [0x3E9, lengths[0] // 4]
    with open(path, "wb") as f:
        f.write(struct.pack(f">{len(longs)}I", *longs))


class HunksTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeAmiberry().start()
        self.addCleanup(self.fake.__exit__)
        self.fake.boot_workbench()
        self.fake.add_shell("C:NewIcons", [14312], name="Background CLI")
        self.memory = Memory(Link(self.fake.path))
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.file = os.path.join(self.dir.name, "OctaMED.patched")
        write_hunk_file(self.file, LENGTHS, chip={2})

    def test_shell_program(self):
        _, segments = self.fake.add_shell("OctaMED.patched", LENGTHS)
        hunks = self.memory.hunks("OctaMED.patched")
        self.assertEqual(hunks, [Hunk(n, a, l) for n, (a, l) in enumerate(segments)])
        self.assertEqual([h.length for h in hunks], LENGTHS)

    def test_name_without_case_or_path(self):
        _, segments = self.fake.add_shell("PC:OctaMED/OctaMED.patched", LENGTHS)
        for name in ("octamed.PATCHED", "PC:OctaMED/OctaMED.patched", "DH1:x/octamed.patched"):
            self.assertEqual([h.address for h in self.memory.hunks(name)], [a for a, _ in segments])

    def test_not_running(self):
        with self.assertRaises(AmiberryError) as e:
            self.memory.hunks("OctaMED.patched")
        self.assertIn("OctaMED.patched isn't running: no Shell is running it", str(e.exception))
        with self.assertRaises(AmiberryError) as e:
            self.memory.hunks(self.file)
        self.assertIn("OctaMED.patched isn't running", str(e.exception))

    def test_running_in_two_shells(self):
        self.fake.add_shell("OctaMED.patched", LENGTHS)
        self.fake.add_shell("PC:OctaMED/OctaMED.patched", LENGTHS)
        with self.assertRaises(AmiberryError) as e:
            self.memory.hunks("OctaMED.patched")
        self.assertIn("running more than once", str(e.exception))
        with self.assertRaises(AmiberryError) as e:
            self.memory.hunks(self.file)
        self.assertIn("running more than once", str(e.exception))

    def test_detached_by_its_name(self):
        _, segments = self.fake.add_detached("Copper", [3000, 200])
        hunks = self.memory.hunks("copper")
        self.assertEqual(hunks, [Hunk(0, segments[0][0], 3000), Hunk(1, segments[1][0], 200)])

    def test_detached_by_hunk_file(self):
        # OctaMED.patched as seen: its start-up (hunk 0) detaches the rest as "OctaMED".
        self.fake.add_shell("", [], name="Shell Process")
        _, segments = self.fake.add_detached("OctaMED", LENGTHS[1:])
        hunks = self.memory.hunks(self.file)
        self.assertEqual(hunks[0], Hunk(0, None, 828))
        self.assertEqual(hunks[1:], [Hunk(n + 1, a, l) for n, (a, l) in enumerate(segments)])
        with self.assertRaises(AmiberryError):
            self.memory.hunks("OctaMED.patched")     # by name it can't be found

    def test_shell_program_by_hunk_file(self):
        _, segments = self.fake.add_shell("OctaMED.patched", LENGTHS)
        self.assertEqual([h.address for h in self.memory.hunks(self.file)], [a for a, _ in segments])

    def test_tail_only_counts_for_a_detached_process(self):
        self.fake.add_shell("Other", LENGTHS[2:])       # a Shell program that happens to fit
        with self.assertRaises(AmiberryError):
            self.memory.hunks(self.file)

    def test_whole_match_is_preferred(self):
        _, segments = self.fake.add_shell("OctaMED.patched", LENGTHS)
        self.fake.add_detached("Odd", LENGTHS[3:])
        self.assertEqual([h.address for h in self.memory.hunks(self.file)], [a for a, _ in segments])

    def test_task_listed_twice_counts_once(self):
        proc, segments = self.fake.add_shell("OctaMED.patched", LENGTHS)
        self.fake.set_this_task(proc)        # also still in the wait list
        self.assertEqual(len(self.memory.hunks("OctaMED.patched")), 4)

    def test_hunk_sizes(self):
        self.assertEqual(hunk_sizes(self.file), LENGTHS)
        bad = os.path.join(self.dir.name, "readme")
        with open(bad, "w") as f:
            f.write("not a program")
        with self.assertRaises(AmiberryError) as e:
            hunk_sizes(bad)
        self.assertIn("isn't an Amiga program", str(e.exception))


if __name__ == "__main__":
    unittest.main()
