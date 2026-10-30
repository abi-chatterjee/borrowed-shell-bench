#!/usr/bin/env python3
"""Smoke check for the PyInstaller variant: run the frozen app as `ui --check`
(server + token guard + window backend import, no window)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import smokelib  # noqa: E402

args = ["ui", "--check"] + (["--skip-backend"] if os.environ.get("SMOKE_SKIP_BACKEND") == "1" else [])
sys.exit(smokelib.main("pyinstaller", args=args, expect="OK benchnotes"))
