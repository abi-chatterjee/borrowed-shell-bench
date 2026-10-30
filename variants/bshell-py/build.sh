#!/bin/sh
# Thin wrapper: the Borrowed Shell sources live in bshell/py.
exec "$(dirname "$0")/../../bshell/py/build.sh" "$@"
