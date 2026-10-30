import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import measure  # noqa: E402


class DiskTests(unittest.TestCase):
    def test_dir_bytes_counts_symlinks_as_links_not_targets(self):
        with tempfile.TemporaryDirectory() as t:
            big = Path(t) / "big.bin"
            big.write_bytes(b"x" * 100_000)
            tree = Path(t) / "tree"
            tree.mkdir()
            (tree / "a.txt").write_bytes(b"y" * 10)
            os.symlink(big, tree / "link")
            apparent, allocated = measure.dir_bytes(tree)
            self.assertLess(apparent, 10_000)  # the 100 KB target is not followed
            self.assertGreaterEqual(allocated, 0)

    def test_missing_path_is_zero(self):
        self.assertEqual(measure.dir_bytes("/nonexistent/xyz"), (0, 0))


class ProcessTests(unittest.TestCase):
    def test_new_processes_found_by_snapshot_diff_including_orphans(self):
        before = measure.snapshot()
        # grandchild reparented away from the harness, like a WKWebView XPC service
        parent = subprocess.Popen([sys.executable, "-c",
                                   "import subprocess,sys,time;"
                                   "subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);"
                                   "time.sleep(0.2)"])
        parent.wait()
        time.sleep(0.3)
        found = measure.new_processes(before, {os.getpid()})
        sleepers = [p for p in found if "python" in p.name().lower()]
        self.assertGreaterEqual(len(sleepers), 1, "orphaned grandchild must be attributed by the diff")
        mem = measure.memory_of(sleepers)
        self.assertGreater(mem["rss_bytes"], 0)
        measure.stop_processes(sleepers)
        time.sleep(0.3)
        self.assertEqual(measure.still_running(sleepers), [])

    def test_pre_existing_processes_are_excluded(self):
        mine = measure.snapshot()
        self.assertEqual([p.pid for p in measure.new_processes(mine) if p.pid == os.getpid()], [])

    def test_parse_footprint(self):
        text = "Footprint: 512 MB (16384 bytes per page)\n"
        self.assertEqual(measure.parse_footprint(text), 512 * 1024 * 1024)
        self.assertIsNone(measure.parse_footprint("nothing here"))


if __name__ == "__main__":
    unittest.main()
