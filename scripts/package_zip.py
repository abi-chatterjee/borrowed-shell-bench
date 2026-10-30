#!/usr/bin/env python3
"""Zip a directory the same way for every variant.

Entries are sorted, symlinks are stored as symlinks, POSIX permission bits are
kept, timestamps are fixed (reproducible), compression is deflate level 6.

usage: package_zip.py SRC_DIR OUT.zip
The contents of SRC_DIR end up at the top level of the archive."""
import os
import stat
import sys
import zipfile
from pathlib import Path

FIXED_TIME = (2020, 1, 1, 0, 0, 0)


def add(zf, path, arcname):
    st = os.lstat(path)
    info = zipfile.ZipInfo(arcname, FIXED_TIME)
    info.create_system = 3  # unix, so external_attr carries the mode
    if stat.S_ISLNK(st.st_mode):
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(info, os.readlink(path))
    elif stat.S_ISDIR(st.st_mode):
        info.external_attr = ((stat.S_IFDIR | 0o755) << 16) | 0x10
        zf.writestr(info, b"")
    else:
        mode = 0o755 if st.st_mode & 0o111 else 0o644
        info.external_attr = (stat.S_IFREG | mode) << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        with open(path, "rb") as f:
            zf.writestr(info, f.read(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)


def package(src, out):
    src, out = Path(src), Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w") as zf:
        for root, dirs, files in os.walk(src):
            dirs.sort()
            for name in sorted(dirs) + sorted(files):
                p = Path(root) / name
                add(zf, p, (p.relative_to(src).as_posix() + ("/" if p.is_dir() and not p.is_symlink() else "")))
    return out


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    print(package(sys.argv[1], sys.argv[2]))
