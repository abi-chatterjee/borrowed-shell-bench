#!/usr/bin/env python3
"""Smoke check for bshell-py: run install.sh / install.ps1 into a scratch directory.
The installer ends with `benchnotes ui --check`, which fetches / from the server,
checks the token guard and imports the window backend (no window is opened)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import smokelib  # noqa: E402

sys.exit(smokelib.main("bshell-py"))
