#!/bin/sh
# Build the Neutralinojs variant: `neu build` with default settings, then a uniform zip of
# the host binary + resources.neu.
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$ROOT/scripts/common.sh"
STAGE=$BUILD/neutralino
rm -rf "$STAGE" "$DIST/neutralino"
mkdir -p "$STAGE"
cp "$ROOT/variants/neutralino/neutralino.config.json" "$ROOT/variants/neutralino/package.json" "$STAGE/"
"$PYTHON" "$ROOT/scripts/stage_frontend.py" neutralino "$STAGE/resources" >/dev/null
mkdir -p "$STAGE/resources/icons" "$STAGE/resources/js"
cp "$ROOT/assets/icons/icon.png" "$STAGE/resources/icons/appIcon.png"
"$PYTHON" "$ROOT/scripts/render.py" "$STAGE" "$VERSION" >/dev/null
cd "$STAGE"
npm install --no-audit --no-fund --no-progress
cp node_modules/@neutralinojs/lib/dist/neutralino.js resources/js/neutralino.js
npx neu update
npx neu build

case $PLATFORM in
    macos-arm64) SUFFIX=mac_arm64 ;;
    macos-x64) SUFFIX=mac_x64 ;;
    windows-x64) SUFFIX=win_x64.exe ;;
    linux-x64) SUFFIX=linux_x64 ;;
    *) echo "unsupported platform $PLATFORM" >&2; exit 1 ;;
esac
BIN=benchnotes-neutralino-$SUFFIX
PACK=$BUILD/neutralino-pack
rm -rf "$PACK"
mkdir -p "$PACK"
cp "dist/benchnotes-neutralino/$BIN" "dist/benchnotes-neutralino/resources.neu" "$PACK/"
chmod +x "$PACK/$BIN"
finish_zip neutralino "$PACK" exe "$BIN" "node=$(node --version)" "neutralinojs=6.10.0" "neu-cli=11.8.0"
