# Sourced by every build.sh (macOS and Linux). POSIX sh.
# The caller sets ROOT first:  ROOT=$(cd "$(dirname "$0")/../.." && pwd)
# Provides: ROOT, VERSION, PLATFORM, DIST, BUILD, PYTHON
set -eu
PYTHON=${PYTHON:-python3}
VERSION=${BENCH_VERSION:-1.0.0}
PLATFORM=$("$PYTHON" "$ROOT/scripts/platform_tag.py")
DIST=${BENCH_DIST:-$ROOT/dist/$PLATFORM}
BUILD=${BENCH_BUILD:-$ROOT/build/$PLATFORM}
export ROOT VERSION PLATFORM DIST BUILD PYTHON

# finish_zip VARIANT SRC_DIR LAUNCH_KIND LAUNCH_PATH [NAME=VERSION ...]
# Zip SRC_DIR into $DIST/VARIANT and write manifest.json. LAUNCH_KIND is app|exe,
# LAUNCH_PATH is relative to the extracted zip.
finish_zip() {
    _v=$1; _src=$2; _lk=$3; _lp=$4; shift 4
    mkdir -p "$DIST/$_v"
    _zip=$_v-$VERSION-$PLATFORM.zip
    "$PYTHON" "$ROOT/scripts/package_zip.py" "$_src" "$DIST/$_v/$_zip" >/dev/null
    _n=$#
    while [ "$_n" -gt 0 ]; do set -- "$@" --tool "$1"; shift; _n=$((_n - 1)); done
    "$PYTHON" "$ROOT/scripts/write_manifest.py" --dir "$DIST/$_v" --variant "$_v" --version "$VERSION" \
        --kind zip --artifact "$_zip" --launch-kind "$_lk" --launch-path "$_lp" "$@"
    echo "$_v built: $DIST/$_v/$_zip"
}
