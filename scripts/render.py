#!/usr/bin/env python3
"""Replace the token @VERSION@ with VERSION in every text file under DIR.

usage: render.py DIR VERSION
Used on staged copies only; the tracked sources keep the token."""
import sys
from pathlib import Path


def render(root, version):
    n = 0
    for p in Path(root).rglob("*"):
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if "@VERSION@" in text:
            p.write_text(text.replace("@VERSION@", version), encoding="utf-8")
            n += 1
    return n


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    print("rendered %d files" % render(*sys.argv[1:]))
