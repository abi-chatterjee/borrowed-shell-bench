#!/bin/sh
# Build the Electron variant: electron-builder --dir (default config, unsigned), then a uniform zip.
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$ROOT/scripts/common.sh"
STAGE=$BUILD/electron
rm -rf "$STAGE" "$DIST/electron"
mkdir -p "$STAGE"
cp "$ROOT/variants/electron/package.json" "$ROOT/variants/electron/main.js" "$ROOT/variants/electron/preload.js" "$STAGE/"
cp "$ROOT/bshell/node/src/store.js" "$STAGE/store.js"
"$PYTHON" "$ROOT/scripts/stage_frontend.py" electron "$STAGE/frontend" >/dev/null
cp "$ROOT/assets/icons/icon.icns" "$ROOT/assets/icons/icon.ico" "$ROOT/assets/icons/icon.png" "$STAGE/"
"$PYTHON" "$ROOT/scripts/render.py" "$STAGE" "$VERSION" >/dev/null
cd "$STAGE"
npm install --no-audit --no-fund --no-progress
export CSC_IDENTITY_AUTO_DISCOVERY=false
npx electron-builder --dir --publish never

PACK=$BUILD/electron-pack
rm -rf "$PACK"
mkdir -p "$PACK"
case $PLATFORM in
    macos-*)
        app=$(find dist -maxdepth 2 -name '*.app' -type d | head -n 1)
        [ -n "$app" ] || { echo "no .app produced" >&2; exit 1; }
        cp -R "$app" "$PACK/"
        LK=app; LP=$(basename "$app") ;;
    windows-*)
        cp -R dist/win-unpacked/. "$PACK/"
        LK=exe; LP="Bench Notes (electron).exe" ;;
    *)
        cp -R dist/linux-unpacked/. "$PACK/"
        LK=exe; LP=benchnotes-electron ;;
esac
finish_zip electron "$PACK" "$LK" "$LP" "node=$(node --version)" "electron=$(node -p "require('electron/package.json').version")" \
    "electron-builder=$(node -p "require('electron-builder/package.json').version")"
