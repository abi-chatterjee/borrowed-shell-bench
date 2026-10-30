#!/bin/sh
# Build the bshell-node artifacts: npm tarball(s), install scripts, manifest.
#   BENCH_VERSION (default 1.0.0), BENCH_UPDATE_VERSION (default 1.0.1)
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$ROOT/scripts/common.sh"
UPDATE_VERSION=${BENCH_UPDATE_VERSION:-1.0.1}
OUT=$DIST/bshell-node
rm -rf "$OUT"
mkdir -p "$OUT"

build_tarball() {
    ver=$1
    stage=$BUILD/bshell-node-$ver/package
    rm -rf "$BUILD/bshell-node-$ver"
    mkdir -p "$stage"
    cp -R "$ROOT/bshell/node/package.json" "$ROOT/bshell/node/README.md" "$ROOT/bshell/node/bin" "$ROOT/bshell/node/src" "$stage/"
    "$PYTHON" "$ROOT/scripts/stage_frontend.py" bshell-node "$stage/frontend" >/dev/null
    cp "$ROOT/assets/icons/icon.icns" "$ROOT/assets/icons/icon.ico" "$stage/"
    printf "'use strict';\nmodule.exports = { version: '%s' };\n" "$ver" >"$stage/src/version.js"
    (cd "$stage" && npm version "$ver" --no-git-tag-version --allow-same-version >/dev/null && npm pack --pack-destination "$OUT" --silent >/dev/null)
}

build_tarball "$VERSION"
build_tarball "$UPDATE_VERSION"
cp "$ROOT/bshell/node/install.sh" "$ROOT/bshell/node/install.ps1" "$OUT/"
TARBALL=benchnotes-$VERSION.tgz
"$PYTHON" "$ROOT/scripts/check_frontend.py" --archive "$OUT/$TARBALL" http

case $PLATFORM in
    windows-*) INSTALLER=install.ps1 ;;
    *) INSTALLER=install.sh ;;
esac
"$PYTHON" "$ROOT/scripts/write_manifest.py" --dir "$OUT" --variant bshell-node --version "$VERSION" \
    --kind installer --installer "$INSTALLER" --artifact "$INSTALLER" --artifact "$TARBALL" \
    --update-artifact "benchnotes-$UPDATE_VERSION.tgz" \
    --tool "node=$(node --version)" --tool "npm=$(npm --version)" --tool "webview-binding=@webviewjs/webview@0.4.9"
echo "bshell-node built in $OUT"
