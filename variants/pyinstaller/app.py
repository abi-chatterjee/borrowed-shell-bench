"""PyInstaller entry point: the same benchnotes package, frozen, variant id 'pyinstaller'.

With no arguments (a double click) it opens the window; `ui --check` is the smoke test."""
import sys

from benchnotes.logs import redirect_std_streams_if_missing

redirect_std_streams_if_missing("pyinstaller")  # windowed builds have no stdout/stderr

from benchnotes.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["ui"], variant="pyinstaller"))
