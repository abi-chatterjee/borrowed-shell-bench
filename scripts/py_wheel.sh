# Sourced after common.sh. build_wheel VERSION OUT_DIR: stage bshell/py with the shared
# frontend and icons, then `pip wheel` it. Used by bshell-py and by the PyInstaller variant
# (which freezes the same package).
build_wheel() {
    _ver=$1; _out=$2
    _stage=$BUILD/wheel-stage-$_ver
    rm -rf "$_stage"
    mkdir -p "$_stage" "$_out"
    cp -R "$ROOT/bshell/py/pyproject.toml" "$ROOT/bshell/py/README.md" "$ROOT/bshell/py/src" "$_stage/"
    find "$_stage" -name __pycache__ -type d -prune -exec rm -rf {} +
    rm -rf "$_stage/src/benchnotes/frontend"
    "$PYTHON" "$ROOT/scripts/stage_frontend.py" bshell-py "$_stage/src/benchnotes/frontend" >/dev/null
    cp "$ROOT/assets/icons/icon.icns" "$ROOT/assets/icons/icon.ico" "$_stage/src/benchnotes/"
    printf '__version__ = "%s"\n' "$_ver" >"$_stage/src/benchnotes/_version.py"
    (cd "$_stage" && "$PYTHON" -m pip wheel . --no-deps --quiet -w "$_out")
}
