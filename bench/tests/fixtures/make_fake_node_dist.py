#!/usr/bin/env python3
"""Build a local stand-in for https://nodejs.org/dist (blocked in the Linux sandbox).

usage: make_fake_node_dist.py OUT_DIR VERSION NODE_BINARY NPM_PACKAGE_DIR

Produces OUT_DIR/v<VERSION>/node-v<VERSION>-linux-x64.tar.gz (bin/node, bin/npm,
lib/node_modules/npm) and SHASUMS256.txt in the same layout nodejs.org uses, so
install.sh can be pointed at it with BENCHNOTES_NODE_DIST_URL=file://OUT_DIR.
Test fixture only; real runs download the official build."""
import hashlib
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path


def main(out, version, node_bin, npm_dir):
    out = Path(out)
    top = "node-v%s-linux-x64" % version
    with tempfile.TemporaryDirectory() as t:
        root = Path(t) / top
        (root / "bin").mkdir(parents=True)
        (root / "lib" / "node_modules").mkdir(parents=True)
        shutil.copy2(node_bin, root / "bin" / "node")
        shutil.copytree(npm_dir, root / "lib" / "node_modules" / "npm", symlinks=True)
        os.symlink("../lib/node_modules/npm/bin/npm-cli.js", root / "bin" / "npm")
        dest = out / ("v" + version)
        dest.mkdir(parents=True, exist_ok=True)
        archive = dest / (top + ".tar.gz")
        with tarfile.open(archive, "w:gz") as tf:
            tf.add(root, arcname=top)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (dest / "SHASUMS256.txt").write_text("%s  %s\n" % (digest, archive.name))
    print(archive)


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    main(*sys.argv[1:])
