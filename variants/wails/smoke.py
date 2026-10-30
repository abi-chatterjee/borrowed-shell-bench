#!/usr/bin/env python3
"""Smoke check for Wails: BENCH_SELFTEST=1 makes the binary exercise its store, print
'OK wails <version>' and exit before wails.Run creates a window."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import smokelib  # noqa: E402

sys.exit(smokelib.main("wails", env={"BENCH_SELFTEST": "1"}, expect="OK wails"))
