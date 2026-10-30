#!/usr/bin/env python3
"""Build a dist/<platform>/ directory with two fake variants for harness tests (Linux/POSIX).

  fake-zip        kind zip: launch.sh + fake_app.py in a zip
  fake-installer  kind installer: install.sh provisions a fake runtime (5 MB) unless a
                  'fakepy' is already on PATH, an app.sh with run/version/update, and logs
                  in the same format as the real installers.

usage: make_dist.py DIST_ROOT   (DIST_ROOT/<variant>/ is created)"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import package_zip  # noqa: E402

INSTALL_SH = r"""#!/bin/sh
set -eu
home=${BENCHNOTES_HOME:?}
apps=${BENCHNOTES_APPS_DIR:?}
art=${BENCHNOTES_WHEEL:?}
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$home/logs" "$apps"
log=$home/logs/install.log
: > "$log"
started=$(date +%s)
runtime_downloaded=no
if [ "${BENCHNOTES_FORCE_RUNTIME_INSTALL:-0}" = 1 ] || ! command -v fakepy >/dev/null 2>&1; then
    mkdir -p "$home/runtime/bin"
    { printf '#!/bin/sh\nexec "$@"\n#'; head -c 5000000 /dev/zero | tr '\0' 'x'; } > "$home/runtime/bin/fakepy"
    chmod +x "$home/runtime/bin/fakepy"
    echo "fetched: fake-runtime 5000000 bytes" >> "$log"
    runtime_downloaded=yes
fi
cp "$here/fake_app.py" "$home/fake_app.py"
cp "$here/app.sh" "$home/app.sh"
chmod +x "$home/app.sh"
basename "$art" | sed 's/^fake-//; s/\.whl$//' > "$home/version"
echo "fetched: pip downloads about 123456 bytes" >> "$log"
{
    echo "runtime_downloaded: $runtime_downloaded"
    echo "install_seconds: $(( $(date +%s) - started ))"
    echo "interpreter: $home/app.sh"
    echo "launch: $home/app.sh run"
    echo "Done."
} >> "$log"
cat "$log"
"""

APP_SH = r"""#!/bin/sh
home=$(cd "$(dirname "$0")" && pwd)
case ${1:-run} in
    version) cat "$home/version" ;;
    update) cp "$2" "$home/payload"; basename "$2" | sed 's/^fake-//; s/\.whl$//' > "$home/version" ;;
    run) exec python3 "$home/fake_app.py" ;;
esac
"""


def manifest(args):
    subprocess.run([sys.executable, str(ROOT / "scripts" / "write_manifest.py")] + args, check=True, capture_output=True)


def main(dist_root):
    dist_root = Path(dist_root)
    # fake-zip
    d = dist_root / "fake-zip"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as t:
        pack = Path(t) / "pack"
        pack.mkdir()
        shutil.copy(HERE / "fake_app.py", pack / "fake_app.py")
        (pack / "launch.sh").write_text('#!/bin/sh\nexec python3 "$(dirname "$0")/fake_app.py"\n')
        (pack / "launch.sh").chmod(0o755)
        package_zip.package(pack, d / "fake-zip-1.0.0-test.zip")
    manifest(["--dir", str(d), "--variant", "fake-zip", "--version", "1.0.0", "--kind", "zip",
              "--artifact", "fake-zip-1.0.0-test.zip", "--launch-kind", "exe", "--launch-path", "launch.sh"])
    # fake-installer
    d = dist_root / "fake-installer"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    (d / "install.sh").write_text(INSTALL_SH)
    (d / "app.sh").write_text(APP_SH)
    shutil.copy(HERE / "fake_app.py", d / "fake_app.py")
    (d / "fake-1.0.0.whl").write_bytes(b"w" * 20000)
    (d / "fake-1.0.1.whl").write_bytes(b"w" * 20100)
    manifest(["--dir", str(d), "--variant", "fake-installer", "--version", "1.0.0", "--kind", "installer",
              "--installer", "install.sh", "--artifact", "install.sh", "--artifact", "fake-1.0.0.whl",
              "--update-artifact", "fake-1.0.1.whl"])
    return dist_root


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(main(sys.argv[1]))
