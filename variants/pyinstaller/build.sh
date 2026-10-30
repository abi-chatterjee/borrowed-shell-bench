#!/bin/sh
# Build the PyInstaller variant: freeze the same benchnotes wheel with PyInstaller defaults
# (onedir, --windowed on macOS/Windows), then a uniform zip.
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$ROOT/scripts/common.sh"
. "$ROOT/scripts/py_wheel.sh"
PYINSTALLER_VERSION=6.22.3
STAGE=$BUILD/pyinstaller
rm -rf "$STAGE" "$DIST/pyinstaller"
mkdir -p "$STAGE"
build_wheel "$VERSION" "$STAGE/wheel"
"$PYTHON" -m venv "$STAGE/venv"
VPY=$STAGE/venv/bin/python
"$VPY" -m pip install --quiet --disable-pip-version-check "$STAGE"/wheel/benchnotes-*.whl "pyinstaller==$PYINSTALLER_VERSION"
cp "$ROOT/variants/pyinstaller/app.py" "$STAGE/app.py"

NAME="Bench Notes (pyinstaller)"
case $PLATFORM in
    macos-*) EXTRA="--windowed --icon $ROOT/assets/icons/icon.icns --osx-bundle-identifier com.gritsa.benchnotes.pyinstaller --hidden-import webview.platforms.cocoa" ;;
    *) EXTRA="" ;;
esac
cd "$STAGE"
# shellcheck disable=SC2086
"$VPY" -m PyInstaller --noconfirm --clean --name "$NAME" --collect-data benchnotes $EXTRA app.py

PACK=$BUILD/pyinstaller-pack
rm -rf "$PACK"
mkdir -p "$PACK"
case $PLATFORM in
    macos-*)
        cp -R "dist/$NAME.app" "$PACK/"
        LK=app; LP="$NAME.app" ;;
    *)
        cp -R "dist/$NAME/." "$PACK/"
        LK=exe; LP=$NAME ;;
esac
finish_zip pyinstaller "$PACK" "$LK" "$LP" "python=$("$VPY" -c 'import sys;print(sys.version.split()[0])')" \
    "pyinstaller=$PYINSTALLER_VERSION" "pywebview=6.2.1"
