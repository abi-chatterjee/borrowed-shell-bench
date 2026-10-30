#!/bin/sh
# Build the Tauri v2 variant with `tauri build` defaults (Cargo release profile untouched), unsigned.
# macOS: --bundles app (a .app, no dmg, so the artifact is comparable to the other zips).
# Elsewhere: --no-bundle (the bare executable).
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$ROOT/scripts/common.sh"
STAGE=$BUILD/tauri
rm -rf "$STAGE" "$DIST/tauri"
mkdir -p "$STAGE"
cp "$ROOT/variants/tauri/package.json" "$STAGE/"
cp -R "$ROOT/variants/tauri/src-tauri" "$STAGE/src-tauri"
mkdir -p "$STAGE/src-tauri/icons"
cp "$ROOT/assets/icons/32x32.png" "$ROOT/assets/icons/128x128.png" "$ROOT/assets/icons/128x128@2x.png" \
   "$ROOT/assets/icons/icon.icns" "$ROOT/assets/icons/icon.ico" "$ROOT/assets/icons/icon.png" "$STAGE/src-tauri/icons/"
"$PYTHON" "$ROOT/scripts/stage_frontend.py" tauri "$STAGE/frontend" >/dev/null
"$PYTHON" "$ROOT/scripts/render.py" "$STAGE" "$VERSION" >/dev/null
cd "$STAGE"
npm install --no-audit --no-fund --no-progress
case $PLATFORM in
    macos-*) npx tauri build --bundles app ;;
    *) npx tauri build --no-bundle ;;
esac

PACK=$BUILD/tauri-pack
rm -rf "$PACK"
mkdir -p "$PACK"
case $PLATFORM in
    macos-*)
        cp -R "src-tauri/target/release/bundle/macos/Bench Notes (tauri).app" "$PACK/"
        LK=app; LP="Bench Notes (tauri).app" ;;
    windows-*)
        cp src-tauri/target/release/benchnotes-tauri.exe "$PACK/"
        LK=exe; LP=benchnotes-tauri.exe ;;
    *)
        cp src-tauri/target/release/benchnotes-tauri "$PACK/"
        LK=exe; LP=benchnotes-tauri ;;
esac
finish_zip tauri "$PACK" "$LK" "$LP" "node=$(node --version)" "rust=$(rustc --version | cut -d' ' -f2)" \
    "tauri-cli=2.12.4" "tauri=$(grep -A1 '^name = "tauri"$' src-tauri/Cargo.lock | grep version | cut -d'"' -f2)"
