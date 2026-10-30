import sys

from .logs import redirect_std_streams_if_missing

# Must run before anything can print: pythonw.exe starts with sys.stdout and
# sys.stderr set to None.
redirect_std_streams_if_missing()

from .cli import main  # noqa: E402

sys.exit(main())
