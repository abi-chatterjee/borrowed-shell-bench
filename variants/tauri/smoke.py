#!/usr/bin/env python3
"""Smoke check for Tauri: BENCH_SELFTEST=1 makes the binary exercise its store, print
'OK tauri <version>' and exit before any window or web view is created."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import smokelib  # noqa: E402

sys.exit(smokelib.main("tauri", env={"BENCH_SELFTEST": "1"}, expect="OK tauri"))
