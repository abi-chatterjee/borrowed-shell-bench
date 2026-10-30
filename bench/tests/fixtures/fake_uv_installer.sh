#!/bin/sh
# Test double for https://astral.sh/uv/install.sh (that host is not reachable
# from the Linux build sandbox). Honors the same variable the installer scripts
# set and copies an already-installed uv into place. Real runs use the real installer.
set -eu
dest=${UV_UNMANAGED_INSTALL:-${UV_INSTALL_DIR:?no install dir given}}
src=${FAKE_UV_BIN:-$(command -v uv)}
mkdir -p "$dest"
cp "$src" "$dest/uv"
chmod +x "$dest/uv"
echo "fake uv installer: copied $src to $dest/uv"
