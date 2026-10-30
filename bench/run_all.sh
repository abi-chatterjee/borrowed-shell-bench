#!/bin/sh
# macOS: install the harness dependency into a private venv, then benchmark every built variant.
#   bench/run_all.sh [RUNS]          (default 5; a quiet machine is required, see docs/method.md)
# Reads dist/macos-<arch>/ (download the CI artifact first, or run scripts/build_all.sh).
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUNS=${1:-5}
if [ ! -x "$ROOT/.venv-bench/bin/python" ]; then
    python3 -m venv "$ROOT/.venv-bench"
fi
"$ROOT/.venv-bench/bin/python" -m pip install --quiet --disable-pip-version-check -r "$ROOT/bench/requirements.txt"
HOST=$(scutil --get LocalHostName 2>/dev/null || hostname -s)
ARCH=$(uname -m)
"$ROOT/.venv-bench/bin/python" "$ROOT/bench/run.py" --variants all --runs "$RUNS" --out "$ROOT/results/$HOST-$ARCH.json"
