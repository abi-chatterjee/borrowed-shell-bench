#!/bin/sh
# Build the Wails v2 variant with `wails build` defaults, unsigned.
# Needs the wails CLI (go install github.com/wailsapp/wails/v2/cmd/wails@v2.17.0) and, on Linux,
# libgtk-3-dev + libwebkit2gtk-4.1-dev (built with -tags webkit2_41; Ubuntu 24.04 has no 4.0).
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$ROOT/scripts/common.sh"
WAILS_VERSION=v2.17.0
STAGE=$BUILD/wails
rm -rf "$STAGE" "$DIST/wails"
mkdir -p "$STAGE/build"
cd "$ROOT/variants/wails"
cp go.mod wails.json version.go main.go app.go "$STAGE/"
[ -f go.sum ] && cp go.sum "$STAGE/"
cp -R store "$STAGE/store"
cp "$ROOT/assets/icons/icon.png" "$STAGE/build/appicon.png"
"$PYTHON" "$ROOT/scripts/stage_frontend.py" wails "$STAGE/frontend" >/dev/null
"$PYTHON" "$ROOT/scripts/render.py" "$STAGE" "$VERSION" >/dev/null
cd "$STAGE"
if ! command -v wails >/dev/null 2>&1; then
    go install "github.com/wailsapp/wails/v2/cmd/wails@$WAILS_VERSION"
    PATH="$(go env GOPATH)/bin:$PATH"
fi
go mod tidy
case $PLATFORM in
    linux-*) TAGS="-tags webkit2_41" ;;
    *) TAGS="" ;;
esac
# shellcheck disable=SC2086
wails build -clean $TAGS

PACK=$BUILD/wails-pack
rm -rf "$PACK"
mkdir -p "$PACK"
case $PLATFORM in
    macos-*)
        cp -R "build/bin/Bench Notes (wails).app" "$PACK/"
        LK=app; LP="Bench Notes (wails).app" ;;
    windows-*)
        cp "build/bin/Bench Notes (wails).exe" "$PACK/"
        LK=exe; LP="Bench Notes (wails).exe" ;;
    *)
        cp "build/bin/Bench Notes (wails)" "$PACK/"
        LK=exe; LP="Bench Notes (wails)" ;;
esac
finish_zip wails "$PACK" "$LK" "$LP" "go=$(go env GOVERSION)" "wails=$WAILS_VERSION"
