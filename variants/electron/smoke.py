#!/usr/bin/env python3
"""Smoke check for the Electron variant (see scripts/smokelib.py)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import smokelib  # noqa: E402

# BENCH_SELFTEST=1 makes the app exercise its store, print 'OK ...' and exit
# before creating a window. Electron still needs a display server to start.
# Chromium refuses to run as root without --no-sandbox (only matters in containers).
args = ["--no-sandbox"] if hasattr(os, "geteuid") and os.geteuid() == 0 else []
sys.exit(smokelib.main("electron", env={"BENCH_SELFTEST": "1"}, args=args, expect="OK electron"))
