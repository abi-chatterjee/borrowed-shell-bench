#!/bin/sh
# Build every variant (or the ones named in $BENCH_VARIANTS, space separated) for this
# machine, then run each variant's smoke check. Every variant is attempted even if an
# earlier one fails; the exit code is non-zero if any build or smoke check failed.
#   scripts/build_all.sh
#   BENCH_VARIANTS="tauri bshell-py" scripts/build_all.sh
#   BENCH_SKIP_SMOKE=1 scripts/build_all.sh
ROOT=$(cd "$(dirname "$0")/.." && pwd)
. "$ROOT/scripts/common.sh"
set +e
LIST=${BENCH_VARIANTS:-electron tauri wails neutralino pyinstaller bshell-py bshell-node}
FAILED=""
SUMMARY=""
for v in $LIST; do
    echo "=== build $v ($PLATFORM) ==="
    if sh "$ROOT/variants/$v/build.sh"; then
        b=built
    else
        b=build_failed
        FAILED="$FAILED $v"
    fi
    s=skipped
    if [ "$b" = built ] && [ -z "${BENCH_SKIP_SMOKE:-}" ]; then
        echo "=== smoke $v ==="
        if "$PYTHON" "$ROOT/variants/$v/smoke.py"; then
            s=ok
        else
            s=smoke_failed
            FAILED="$FAILED $v"
        fi
    fi
    SUMMARY="$SUMMARY
$v: $b, smoke $s"
done
echo "=== summary for $PLATFORM ===$SUMMARY"
if [ -n "$FAILED" ]; then
    echo "failed:$FAILED" >&2
    exit 1
fi
