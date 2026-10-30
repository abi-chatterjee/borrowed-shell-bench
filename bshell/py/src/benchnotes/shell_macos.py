"""Build the native macOS shell: a minimal .app around the venv's interpreter.

Layout (all of it is symlinks and small text files, about 10 KB):

  Bench Notes (bshell-py).app/Contents/        (sys.prefix: CPython takes the parent of
                                                the directory holding the symlinked
                                                interpreter and its pyvenv.cfg)
    Info.plist                       own bundle id and name
    MacOS/launch                     shell script: logs, then execs BenchNotes
    MacOS/BenchNotes -> <real interpreter Mach-O>
    MacOS/pyvenv.cfg                 makes the symlinked interpreter a venv
    lib/pythonX.Y/site-packages -> <venv>/lib/pythonX.Y/site-packages
    Resources/icon.icns

The process is the real Python Mach-O running *inside* the bundle's MacOS
directory, so the OS gives it the bundle's identity (Dock name, icon, bundle
id) instead of a generic 'Python' entry.
"""
import os
import plistlib
import shutil
import subprocess
import sys
import sysconfig
import time
from pathlib import Path

from ._version import __version__

APP_NAME = "Bench Notes (bshell-py)"
BUNDLE_ID = "com.gritsa.benchnotes.bshellpy"
EXE = "BenchNotes"


def default_apps_dir():
    return str(Path.home() / "Applications")


def real_interpreter(base_executable=None, base_prefix=None, framework=None):
    """Resolve the interpreter Mach-O behind sys._base_executable.

    On framework builds (python.org, Homebrew) bin/python3.X is a small stub
    that execs Resources/Python.app/Contents/MacOS/Python; the stub cannot be
    used as the bundle executable, the real binary can. Standalone builds
    (uv, python-build-standalone) have no stub and resolve to themselves."""
    base_executable = base_executable or getattr(sys, "_base_executable", sys.executable)
    base_prefix = base_prefix or sys.base_prefix
    if framework is None:
        framework = sysconfig.get_config_var("PYTHONFRAMEWORK")
    if framework:
        inner = Path(base_prefix) / "Resources" / "Python.app" / "Contents" / "MacOS" / framework
        if inner.exists():
            return Path(os.path.realpath(inner))
    return Path(os.path.realpath(base_executable))


def launcher_script():
    return """#!/bin/sh
# Bench Notes (bshell-py) launcher. stdout/stderr go to a log file because a
# GUI app launched from Finder has no terminal.
here=$(cd "$(dirname "$0")" && pwd)
log_dir="${BENCHNOTES_LOG_DIR:-$HOME/Library/Logs/BenchNotes}"
mkdir -p "$log_dir"
exec "$here/%s" -m benchnotes ui "$@" >>"$log_dir/bshell-py.log" 2>&1
""" % EXE


def info_plist():
    return {
        "CFBundleName": "Bench Notes",
        "CFBundleDisplayName": "Bench Notes",
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleVersion": __version__,
        "CFBundleShortVersionString": __version__,
        "CFBundleExecutable": "launch",
        "CFBundleIconFile": "icon",
        "CFBundlePackageType": "APPL",
        "CFBundleInfoDictionaryVersion": "6.0",
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        # The web view loads http://127.0.0.1:<port>; ATS must allow loopback.
        "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
    }


def pyvenv_cfg(real_exe, venv):
    """pyvenv.cfg for the in-bundle 'venv'. Reuses the venv's own settings
    except for home/executable, which point at the real interpreter."""
    version = "%d.%d.%d" % sys.version_info[:3]
    return (
        "home = %s\n"
        "include-system-site-packages = false\n"
        "version = %s\n"
        "executable = %s\n"
        "command = %s -m venv %s\n"
    ) % (real_exe.parent, version, real_exe, real_exe, venv)


def assemble(app_dir, venv, icon=None, real_exe=None):
    """Create the bundle contents in app_dir (must not exist)."""
    venv = Path(venv)
    real_exe = real_exe or real_interpreter()
    macos = app_dir / "Contents" / "MacOS"
    res = app_dir / "Contents" / "Resources"
    macos.mkdir(parents=True)
    res.mkdir(parents=True)
    with open(app_dir / "Contents" / "Info.plist", "wb") as f:
        plistlib.dump(info_plist(), f)
    launch = macos / "launch"
    launch.write_text(launcher_script(), encoding="utf-8")
    launch.chmod(0o755)
    os.symlink(real_exe, macos / EXE)
    (macos / "pyvenv.cfg").write_text(pyvenv_cfg(real_exe, venv), encoding="utf-8")
    pyver = "python%d.%d" % sys.version_info[:2]
    site = venv / "lib" / pyver / "site-packages"
    (app_dir / "Contents" / "lib" / pyver).mkdir(parents=True)
    os.symlink(site, app_dir / "Contents" / "lib" / pyver / "site-packages")
    if icon is None:
        packaged = Path(__file__).with_name("icon.icns")
        icon = packaged if packaged.exists() else None
    if icon and Path(icon).exists():
        shutil.copyfile(icon, res / "icon.icns")


def self_test(app_dir, skip_backend=False):
    args = [str(app_dir / "Contents" / "MacOS" / "launch"), "--check"]
    if skip_backend:
        args.append("--skip-backend")
    log_dir = app_dir.parent / ".selftest-logs"
    env = dict(os.environ, BENCHNOTES_LOG_DIR=str(log_dir))
    r = subprocess.run(args, env=env, timeout=120)
    log = log_dir / "bshell-py.log"
    tail = log.read_text(errors="replace")[-2000:] if log.exists() else "(no log)"
    shutil.rmtree(log_dir, ignore_errors=True)
    if r.returncode != 0:
        raise RuntimeError("shell self-test failed (exit %d). Log tail:\n%s" % (r.returncode, tail))


def build(apps_dir=None, venv=None, skip_backend=False, real_exe=None, icon=None):
    """Build in a staging directory, self-test it, then swap it into place."""
    apps = Path(apps_dir or os.environ.get("BENCHNOTES_APPS_DIR") or default_apps_dir())
    venv = Path(venv or sys.prefix)
    apps.mkdir(parents=True, exist_ok=True)
    final = apps / (APP_NAME + ".app")
    staging = apps / ("." + APP_NAME + ".app.staging")
    if staging.exists():
        shutil.rmtree(staging)
    try:
        assemble(staging, venv, icon=icon, real_exe=real_exe)
        self_test(staging, skip_backend=skip_backend)
        old = None
        if final.exists():
            old = apps / ("." + APP_NAME + ".app.old-%d" % int(time.time()))
            os.rename(final, old)
        os.rename(staging, final)
        if old:
            shutil.rmtree(old, ignore_errors=True)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    return final
