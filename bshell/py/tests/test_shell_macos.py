import os
import plistlib
import sys
import tempfile
import unittest
from pathlib import Path

from benchnotes import shell_macos


class ShellPureTests(unittest.TestCase):
    def test_framework_stub_is_resolved_to_inner_binary(self):
        with tempfile.TemporaryDirectory() as t:
            prefix = Path(t) / "Python.framework" / "Versions" / "3.12"
            inner = prefix / "Resources" / "Python.app" / "Contents" / "MacOS" / "Python"
            inner.parent.mkdir(parents=True)
            inner.write_text("macho")
            (prefix / "bin").mkdir()
            stub = prefix / "bin" / "python3.12"
            stub.write_text("stub")
            got = shell_macos.real_interpreter(str(stub), str(prefix), framework="Python")
            self.assertEqual(got, inner.resolve())

    def test_standalone_build_resolves_symlink_chain(self):
        with tempfile.TemporaryDirectory() as t:
            real = Path(t) / "real" / "python3.12"
            real.parent.mkdir()
            real.write_text("macho")
            link = Path(t) / "bin-python"
            os.symlink(real, link)
            self.assertEqual(shell_macos.real_interpreter(str(link), t, framework=""), real.resolve())

    def test_plist_and_launcher(self):
        plist = shell_macos.info_plist()
        self.assertEqual(plist["CFBundleExecutable"], "launch")
        self.assertEqual(plist["CFBundleIdentifier"], "com.gritsa.benchnotes.bshellpy")
        plistlib.dumps(plist)  # serialisable
        script = shell_macos.launcher_script()
        self.assertTrue(script.startswith("#!/bin/sh"))
        self.assertIn('exec "$here/BenchNotes" -m benchnotes ui "$@"', script)


@unittest.skipUnless(os.environ.get("BENCHNOTES_TEST_VENV_PYTHON"),
                     "set BENCHNOTES_TEST_VENV_PYTHON to a venv python with benchnotes installed")
class ShellLayoutOnLinux(unittest.TestCase):
    """Runs the same symlink + pyvenv.cfg layout the macOS shell uses, on Linux.

    This proves the interpreter-in-a-bundle mechanism with a standalone CPython;
    it does not prove anything about Mach-O, Info.plist handling or LaunchServices."""

    def test_build_and_selftest(self):
        import subprocess
        py = os.environ["BENCHNOTES_TEST_VENV_PYTHON"]
        with tempfile.TemporaryDirectory() as t:
            r = subprocess.run([py, "-m", "benchnotes", "shell", "build", "--apps-dir", t, "--skip-backend"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            app = Path(t) / "Bench Notes (bshell-py).app"
            exe = app / "Contents" / "MacOS" / "BenchNotes"
            self.assertTrue(exe.is_symlink())
            self.assertTrue((app / "Contents" / "MacOS" / "pyvenv.cfg").exists())
            self.assertFalse(any(p.name.startswith(".") for p in Path(t).iterdir()),
                             "staging/old directories must be cleaned up")
            # Rebuild over an existing app (swap path).
            r = subprocess.run([py, "-m", "benchnotes", "shell", "build", "--apps-dir", t, "--skip-backend"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            # The bundle's own interpreter really runs from the bundle and sees the venv.
            out = subprocess.run([str(exe), "-c", "import sys, benchnotes; print(sys.prefix + chr(124) + benchnotes.__file__)"],
                                 capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            prefix, module_file = out.stdout.strip().split("|")
            self.assertEqual(prefix, str(app / "Contents"))  # the bundle acts as the venv prefix
            self.assertIn(str(app / "Contents" / "lib"), module_file)  # benchnotes came via the symlink


if __name__ == "__main__":
    unittest.main()
