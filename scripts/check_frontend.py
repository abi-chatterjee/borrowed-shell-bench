#!/usr/bin/env python3
"""Verify that a staged frontend is the shared frontend plus one adapter.

usage:
  check_frontend.py --all                  stage every variant to a temp dir and compare
  check_frontend.py --dir DIR TRANSPORT    check one directory
  check_frontend.py --archive FILE TRANSPORT   check a .whl/.zip/.tgz (finds the frontend dir inside)

Prints the sha256 over all non-adapter files; it must be identical for all variants."""
import hashlib
import json
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend"


def shared_files(base):
    base = Path(base)
    return sorted(p.relative_to(base).as_posix() for p in base.rglob("*")
                  if p.is_file() and not p.relative_to(base).as_posix().startswith("api/"))


def shared_hash(base):
    h = hashlib.sha256()
    for rel in shared_files(base):
        h.update(rel.encode() + b"\0" + (Path(base) / rel).read_bytes() + b"\0")
    return h.hexdigest()


def check_dir(base, transport):
    base = Path(base)
    if shared_files(base) != shared_files(SRC):
        raise SystemExit("file list differs from frontend/: %s" % base)
    for rel in shared_files(SRC):
        if (base / rel).read_bytes() != (SRC / rel).read_bytes():
            raise SystemExit("content differs from frontend/%s in %s" % (rel, base))
    api = sorted(p.name for p in (base / "api").iterdir())
    if api != ["adapter.js"]:
        raise SystemExit("api/ must contain only adapter.js, found %s" % api)
    if (base / "api" / "adapter.js").read_bytes() != (SRC / "api" / (transport + ".js")).read_bytes():
        raise SystemExit("adapter.js is not frontend/api/%s.js" % transport)
    return shared_hash(base)


def check_archive(path, transport):
    with tempfile.TemporaryDirectory() as tmp:
        path = str(path)
        if path.endswith((".whl", ".zip")):
            zipfile.ZipFile(path).extractall(tmp)
        else:
            tarfile.open(path).extractall(tmp)
        hits = [p.parent for p in Path(tmp).rglob("index.html")
                if (p.parent / "app.js").exists() and (p.parent / "api" / "adapter.js").exists()]
        if len(hits) != 1:
            raise SystemExit("expected exactly one staged frontend in %s, found %d" % (path, len(hits)))
        return check_dir(hits[0], transport)


def main(argv):
    if argv[:1] == ["--all"]:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import stage_frontend
        variants = json.loads((ROOT / "variants" / "variants.json").read_text())
        hashes = {}
        with tempfile.TemporaryDirectory() as tmp:
            for v in variants:
                hashes[v] = stage_frontend.stage(v, Path(tmp) / v) and check_dir(Path(tmp) / v, variants[v]["transport"])
        for v, h in hashes.items():
            print("%-12s %s" % (v, h))
        if len(set(hashes.values())) != 1:
            raise SystemExit("shared frontend hashes differ")
        print("OK: all %d variants share identical non-adapter files" % len(hashes))
    elif argv[:1] == ["--dir"] and len(argv) == 3:
        print(check_dir(argv[1], argv[2]))
    elif argv[:1] == ["--archive"] and len(argv) == 3:
        print(check_archive(argv[1], argv[2]))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
