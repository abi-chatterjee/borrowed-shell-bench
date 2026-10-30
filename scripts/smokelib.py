"""Shared helpers for variants/<id>/smoke.py.

A smoke check answers one question: does the built artifact run at all, without
a human and, where the framework allows, without opening a window?

  * zip variants: extract the zip from dist/<platform>/<variant>/, find the
    launch target named in manifest.json, run it with the variant's headless
    self-test arguments/environment, require exit 0 and an expected line.
  * installer variants: run the installer into a scratch directory (that includes
    the variant's own --check self-test) and require exit 0.

Environment:
  BENCH_DIST        dist root (default dist/<platform>)
  SMOKE_SKIP_BACKEND=1   installer variants: pass BENCHNOTES_SKIP_BACKEND_CHECK=1
                         (Linux sandbox only; real macOS/Windows runs must not set it)
  SMOKE_XVFB=1      wrap the launch in xvfb-run (Linux without a display)
"""
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import platform_tag  # noqa: E402


def dist_dir(variant):
    base = Path(os.environ.get("BENCH_DIST") or ROOT / "dist" / platform_tag.tag())
    return base / variant


def load_manifest(variant):
    path = dist_dir(variant) / "manifest.json"
    if not path.exists():
        raise SystemExit("SMOKE FAIL %s: %s not found (build first)" % (variant, path))
    return json.loads(path.read_text())


def extract(zip_path, dest):
    if os.name == "nt":
        zipfile.ZipFile(zip_path).extractall(dest)
    else:  # unzip keeps symlinks and permission bits, which .app bundles need
        subprocess.run(["unzip", "-q", str(zip_path), "-d", str(dest)], check=True)


def launch_command(manifest, root):
    launch = manifest["launch"]
    target = Path(root) / launch["path"]
    if launch["kind"] == "app":
        plist = plistlib.loads((target / "Contents" / "Info.plist").read_bytes())
        return [str(target / "Contents" / "MacOS" / plist["CFBundleExecutable"])]
    return [str(target)]


def _wrap_display(cmd):
    if os.environ.get("SMOKE_XVFB") == "1":
        return ["xvfb-run", "-a"] + cmd
    return cmd


def main(variant, env=None, args=(), expect=None, timeout=90):
    m = load_manifest(variant)
    d = dist_dir(variant)
    for name, size in m["artifacts"].items():
        if not (d / name).is_file() or (d / name).stat().st_size != size:
            raise SystemExit("SMOKE FAIL %s: artifact %s missing or size changed" % (variant, name))
    if m["kind"] == "installer":
        return run_installer(variant, m, d, timeout)
    with tempfile.TemporaryDirectory() as tmp:
        zips = [n for n in m["artifacts"] if n.endswith(".zip")]
        extract(d / zips[0], tmp)
        cmd = _wrap_display(launch_command(m, tmp) + list(args))
        if not Path(cmd[-len(args) - 1] if args else cmd[-1]).exists() and "xvfb-run" not in cmd[0]:
            raise SystemExit("SMOKE FAIL %s: launch target missing: %s" % (variant, cmd[0]))
        run_env = dict(os.environ, BENCH_DATA_DIR=str(Path(tmp) / "data"), **(env or {}))
        r = subprocess.run(cmd, env=run_env, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode != 0 or (expect and expect not in out):
            raise SystemExit("SMOKE FAIL %s: exit %s, expected %r in output:\n%s" % (variant, r.returncode, expect, out[-2000:]))
    print("SMOKE OK %s (%s)" % (variant, " ".join(cmd[:1])))
    return 0


def run_installer(variant, m, d, timeout):
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "home"
        env = dict(os.environ, HOME=str(Path(tmp) / "user"), BENCHNOTES_HOME=str(home),
                   BENCHNOTES_APPS_DIR=str(Path(tmp) / "apps"))
        Path(env["HOME"]).mkdir()
        artifact = [n for n in m["artifacts"] if n.endswith((".whl", ".tgz"))][0]
        env["BENCHNOTES_WHEEL" if artifact.endswith(".whl") else "BENCHNOTES_TARBALL"] = str(d / artifact)
        if os.environ.get("SMOKE_SKIP_BACKEND") == "1":
            env["BENCHNOTES_SKIP_BACKEND_CHECK"] = "1"
        installer = d / m["installer"]
        if installer.suffix == ".ps1":
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(installer)]
        else:
            cmd = ["sh", str(installer)]
        r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=max(timeout, 600))
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode != 0 or "Done." not in out:
            raise SystemExit("SMOKE FAIL %s: installer exit %s:\n%s" % (variant, r.returncode, out[-3000:]))
    print("SMOKE OK %s (installer ran, self-test passed)" % variant)
    return 0
