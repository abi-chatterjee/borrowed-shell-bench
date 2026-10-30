"""OS-specific launching. Everything else in the harness is OS neutral.

The harness launches the way a user would: `open -n` on a macOS .app, the Start-menu
shortcut (or the exe) on Windows. Environment for the app (BENCH_READY_FILE,
BENCH_DATA_DIR) cannot be passed through `open`, so on macOS it is set in the user's
launchd session with `launchctl setenv` for the duration of the launch and removed
afterwards. Linux support exists only so the harness can be tested in a Linux sandbox
(fake apps, optionally real apps under xvfb); it is not a benchmark platform."""
import os
import shutil
import subprocess
import sys

from measure import now_ms


def platform_name():
    return {"darwin": "macos", "win32": "windows"}.get(sys.platform, "linux")


class Launcher:
    """Context manager: sets up the app environment, launches, tears the environment down."""

    def __init__(self, env):
        self.env = dict(env)
        self._set = []
        self._saved = {}

    def __enter__(self):
        if sys.platform == "darwin":
            for k, v in self.env.items():
                subprocess.run(["launchctl", "setenv", k, v], check=True)
                self._set.append(k)
        elif sys.platform == "win32":
            for k, v in self.env.items():  # os.startfile inherits this process's environment
                self._saved[k] = os.environ.get(k)
                os.environ[k] = v
        return self

    def __exit__(self, *exc):
        for k in self._set:
            subprocess.run(["launchctl", "unsetenv", k], check=False)
        for k, old in self._saved.items():
            if old is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old
        return False

    def launch(self, target):
        """Start the app; return the epoch-ms timestamp taken immediately before the call."""
        kind = target["kind"]
        child_env = dict(os.environ, **self.env)
        if kind == "app":  # macOS bundle
            t0 = now_ms()
            subprocess.run(["open", "-n", target["path"]], check=True)
        elif kind == "lnk":  # Windows Start-menu shortcut
            t0 = now_ms()
            os.startfile(target["path"])  # noqa: Windows only
        else:  # exe (path) or cmd (argv list)
            argv = [target["path"]] if kind == "exe" else list(target["cmd"])
            argv = _display_wrap(argv)
            kwargs = {"env": child_env, "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                      "stderr": subprocess.DEVNULL}
            if os.name == "nt":
                kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | NEW_PROCESS_GROUP
            else:
                kwargs["start_new_session"] = True
            t0 = now_ms()
            subprocess.Popen(argv, **kwargs)
        return t0


def _display_wrap(argv):
    """Linux test runs only: BENCH_XVFB=1 runs GUI apps under xvfb-run (its processes then
    count toward memory, so such numbers are for exercising the harness, never for reporting)."""
    if sys.platform.startswith("linux") and os.environ.get("BENCH_XVFB") == "1" and shutil.which("xvfb-run"):
        return ["xvfb-run", "-a"] + argv
    return argv


def extract_zip(zip_path, dest):
    os.makedirs(dest, exist_ok=True)
    if os.name == "nt":
        import zipfile
        zipfile.ZipFile(zip_path).extractall(dest)
    else:  # unzip keeps symlinks and mode bits (needed for .app bundles)
        subprocess.run(["unzip", "-q", "-o", str(zip_path), "-d", str(dest)], check=True)


def installer_command(installer_path):
    if str(installer_path).endswith(".ps1"):
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(installer_path)]
    return ["sh", str(installer_path)]
