#!/bin/sh
# Thin wrapper: the Borrowed Shell sources live in bshell/node.
exec "$(dirname "$0")/../../bshell/node/build.sh" "$@"
