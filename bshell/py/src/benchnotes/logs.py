"""Log file handling. pythonw.exe has no stdout/stderr, so redirect to a file."""
import os
import sys
from pathlib import Path

from .store import data_dir


def log_dir(variant="bshell-py"):
    override = os.environ.get("BENCHNOTES_LOG_DIR")
    if override:
        return Path(override)
    return data_dir(variant) / "logs"


def redirect_std_streams_if_missing(variant=None):
    """If stdout or stderr is None (pythonw), point both at a log file.

    Returns the log path used, or None when nothing was redirected."""
    if sys.stdout is not None and sys.stderr is not None:
        return None
    variant = variant or os.environ.get("BENCH_VARIANT") or "bshell-py"
    try:
        d = log_dir(variant)
        d.mkdir(parents=True, exist_ok=True)
        path = d / "benchnotes.log"
        stream = open(path, "a", buffering=1, encoding="utf-8", errors="replace")
    except OSError:
        stream = open(os.devnull, "w")
        path = None
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream
    return path
