import io
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

from benchnotes import logs, store, update, winpreflight
from benchnotes.store import NoteStore, data_dir


class StoreTests(unittest.TestCase):
    def test_data_dir_per_platform(self):
        env = {"HOME": "/h", "LOCALAPPDATA": "C:\\L"}
        self.assertEqual(data_dir("v", env, "darwin"), Path("/h/Library/Application Support/BenchNotes/v"))
        self.assertEqual(data_dir("v", env, "win32"), Path("C:\\L") / "BenchNotes" / "v")
        self.assertEqual(data_dir("v", env, "linux"), Path("/h/.local/share/BenchNotes/v"))
        self.assertEqual(data_dir("v", dict(env, BENCH_DATA_DIR="/x"), "darwin"), Path("/x"))

    def test_save_list_remove_and_corrupt_file(self):
        with tempfile.TemporaryDirectory() as t:
            s = NoteStore(t)
            n = s.save({"title": "a", "body": "b"})
            self.assertEqual(s.list(), [n])
            self.assertTrue(s.remove(n["id"]))
            self.assertFalse(s.remove(n["id"]))
            Path(t, "notes.json").write_text("{broken")
            self.assertEqual(s.list(), [])
            self.assertTrue(Path(t, "notes.corrupt").exists())


class LogsTests(unittest.TestCase):
    def test_redirect_only_when_streams_missing(self):
        with tempfile.TemporaryDirectory() as t:
            old = (sys.stdout, sys.stderr)
            os.environ["BENCHNOTES_LOG_DIR"] = t
            try:
                self.assertIsNone(logs.redirect_std_streams_if_missing())
                sys.stdout = sys.stderr = None
                path = logs.redirect_std_streams_if_missing()
                print("hello from pythonw")
                sys.stdout.flush()
                self.assertEqual(Path(path).parent, Path(t))
                self.assertIn("hello from pythonw", Path(path).read_text())
            finally:
                if sys.stdout is not None and sys.stdout is not old[0]:
                    sys.stdout.close()
                sys.stdout, sys.stderr = old
                del os.environ["BENCHNOTES_LOG_DIR"]


class FakeWinreg:
    HKEY_LOCAL_MACHINE = "HKLM"
    HKEY_CURRENT_USER = "HKCU"
    KEY_READ = 0

    def __init__(self, values):
        self.values = values  # {(hive, key, name): value}

    def OpenKey(self, hive, key, reserved, access):
        outer = self

        class K:
            def __enter__(s):
                return (hive, key)

            def __exit__(s, *a):
                return False

        if not any(h == hive and k == key for (h, k, _n) in self.values):
            raise FileNotFoundError(key)
        return K()

    def QueryValueEx(self, k, name):
        try:
            return (self.values[(k[0], k[1], name)], 1)
        except KeyError:
            raise FileNotFoundError(name)


WV2 = r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
NET = r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full"


class WinPreflightTests(unittest.TestCase):
    def test_all_present(self):
        w = FakeWinreg({("HKLM", WV2, "pv"): "120.0.1", ("HKLM", NET, "Release"): 528040})
        self.assertEqual(winpreflight.problems(w), [])

    def test_missing_webview2(self):
        w = FakeWinreg({("HKLM", NET, "Release"): 528040})
        p = winpreflight.problems(w)
        self.assertEqual(len(p), 1)
        self.assertIn("WebView2", p[0])

    def test_placeholder_version_counts_as_missing(self):
        w = FakeWinreg({("HKLM", WV2, "pv"): "0.0.0.0", ("HKLM", NET, "Release"): 528040})
        self.assertIn("WebView2", winpreflight.problems(w)[0])

    def test_old_dotnet(self):
        w = FakeWinreg({("HKLM", WV2, "pv"): "120.0.1", ("HKLM", NET, "Release"): 460798})
        p = winpreflight.problems(w)
        self.assertEqual(len(p), 1)
        self.assertIn("4.7.2", p[0])

    def test_nothing_installed_gives_two_sentences(self):
        self.assertEqual(len(winpreflight.problems(FakeWinreg({}))), 2)


class UpdateTests(unittest.TestCase):
    def test_offline_first_then_online_fallback(self):
        calls = []

        def run(cmd):
            calls.append(cmd)
            return types.SimpleNamespace(returncode=1 if "--no-index" in cmd else 0)

        out = io.StringIO()
        self.assertEqual(update.update(wheel="/w/x.whl", run=run, out=lambda s: out.write(s)), 0)
        self.assertEqual(len(calls), 2)
        self.assertIn("--no-index", calls[0])
        self.assertIn("--upgrade", calls[0])
        self.assertNotIn("--no-index", calls[1])

    def test_offline_success_stops(self):
        calls = []

        def run(cmd):
            calls.append(cmd)
            return types.SimpleNamespace(returncode=0)

        self.assertEqual(update.update(wheel="/w/x.whl", run=run, out=lambda s: None), 0)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
