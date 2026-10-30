#!/bin/sh
# Build the bshell-py artifacts: wheel(s), install.sh, install.ps1, manifest.
#   BENCH_VERSION (default 1.0.0)  version of the main wheel
#   BENCH_UPDATE_VERSION (default 1.0.1)  second wheel, used to measure update cost
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$ROOT/scripts/common.sh"
. "$ROOT/scripts/py_wheel.sh"
UPDATE_VERSION=${BENCH_UPDATE_VERSION:-1.0.1}
OUT=$DIST/bshell-py
rm -rf "$OUT"
mkdir -p "$OUT"

build_wheel "$VERSION" "$OUT"
build_wheel "$UPDATE_VERSION" "$OUT"
cp "$ROOT/bshell/py/install.sh" "$ROOT/bshell/py/install.ps1" "$OUT/"
WHEEL=benchnotes-$VERSION-py3-none-any.whl
"$PYTHON" "$ROOT/scripts/check_frontend.py" --archive "$OUT/$WHEEL" http

case $PLATFORM in
    windows-*) INSTALLER=install.ps1 ;;
    *) INSTALLER=install.sh ;;
esac
"$PYTHON" "$ROOT/scripts/write_manifest.py" --dir "$OUT" --variant bshell-py --version "$VERSION" \
    --kind installer --installer "$INSTALLER" --artifact "$INSTALLER" --artifact "$WHEEL" \
    --update-artifact "benchnotes-$UPDATE_VERSION-py3-none-any.whl" \
    --tool "python=$("$PYTHON" -c 'import sys;print(sys.version.split()[0])')" \
    --tool "pywebview=6.2.1" --tool "hatchling=1.32.4"
echo "bshell-py built in $OUT"
