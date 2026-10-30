#!/usr/bin/env python3
"""Smoke check for Neutralinojs: the zip must contain the host binary and resources.neu and
the binary must be executable. Neutralino has no backend process and no headless mode (the
notes logic lives in the page), so a real launch is covered by the harness (bench/run.py), not here."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import smokelib  # noqa: E402

m = smokelib.load_manifest("neutralino")
d = smokelib.dist_dir("neutralino")
with tempfile.TemporaryDirectory() as tmp:
    smokelib.extract(d / [n for n in m["artifacts"] if n.endswith(".zip")][0], tmp)
    binary = Path(tmp) / m["launch"]["path"]
    ok = binary.is_file() and (Path(tmp) / "resources.neu").is_file() and (os.name == "nt" or os.access(binary, os.X_OK))
    sys.exit(0 if ok else "SMOKE FAIL neutralino: binary or resources.neu missing / not executable")
