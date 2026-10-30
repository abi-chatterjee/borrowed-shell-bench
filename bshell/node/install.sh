#!/bin/sh
# Bench Notes (bshell-node) installer for macOS (and Linux, without the shell step).
#
#   curl -fsSL <url>/install.sh | sh
#
# Per user, never with sudo:
#   1. find Node.js 24+ (or download a private official build, checksum-verified)
#   2. npm install the benchnotes tarball (and the native web view library) under $BENCHNOTES_HOME
#   3. macOS: build "Bench Notes (bshell-node).app" in $BENCHNOTES_APPS_DIR
#   4. run the self-test (benchnotes ui --check)
#
# Node 24+ is required because the platform packages of @webviewjs/webview
# declare engines.node >= 24 (npm silently skips them on older Node).
#
# Environment overrides (all optional):
#   BENCHNOTES_HOME                  install root          (default ~/.benchnotes-node)
#   BENCHNOTES_APPS_DIR              where the .app goes   (default ~/Applications)
#   BENCHNOTES_TARBALL               local tarball path or URL (default: "benchnotes" from the npm registry)
#   BENCHNOTES_NODE_VERSION          Node downloaded when none is usable (default 24.22.1)
#   BENCHNOTES_NODE_DIST_URL         Node download base    (default https://nodejs.org/dist)
#   BENCHNOTES_FORCE_RUNTIME_INSTALL 1 = ignore any Node found, download one (used to measure "runtime absent")
#   BENCHNOTES_SKIP_BACKEND_CHECK    1 = self-test without the window backend (CI/Linux only)
#
# Everything lives inside main(), called on the last line.

main() {
    set -eu

    home_dir=${BENCHNOTES_HOME:-$HOME/.benchnotes-node}
    apps_dir=${BENCHNOTES_APPS_DIR:-$HOME/Applications}
    tarball=${BENCHNOTES_TARBALL:-benchnotes}
    node_want=${BENCHNOTES_NODE_VERSION:-24.22.1}
    dist_url=${BENCHNOTES_NODE_DIST_URL:-https://nodejs.org/dist}
    force_runtime=${BENCHNOTES_FORCE_RUNTIME_INSTALL:-0}
    os=$(uname -s)

    mkdir -p "$home_dir/logs"
    log_file=$home_dir/logs/install.log
    : >"$log_file"
    tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/benchnotes-install.XXXXXX")
    started=$(date +%s)

    log() { printf '%s\n' "$*" | tee -a "$log_file"; }
    fail() {
        log "ERROR: $*"
        log "Details are in $log_file"
        exit 1
    }
    cleanup() {
        status=$?
        rm -rf "$tmp_dir"
        if [ "$status" -ne 0 ]; then
            printf 'Install failed (exit %s). Last log lines:\n' "$status" >&2
            tail -n 15 "$log_file" >&2 || true
        fi
    }
    trap cleanup EXIT

    run() {
        what=$1
        shift
        log "-> $what"
        if ! "$@" >>"$log_file" 2>&1; then
            fail "$what failed"
        fi
    }

    file_size() { wc -c <"$1" | tr -d ' '; }

    sha256_of() {
        if command -v sha256sum >/dev/null 2>&1; then
            sha256sum "$1" | cut -d' ' -f1
        else
            shasum -a 256 "$1" | cut -d' ' -f1
        fi
    }

    # ---- 1. Node.js -----------------------------------------------------------
    node_ok() {
        # usable = major >= 24 and an npm next to it
        major=$("$1" -p 'process.versions.node.split(".")[0]' 2>/dev/null) || return 1
        [ "$major" -ge 24 ] 2>/dev/null || return 1
        [ -x "$(dirname "$1")/npm" ]
    }

    node_bin=
    runtime_downloaded=no
    if [ "$force_runtime" != 1 ]; then
        cand=$(command -v node 2>/dev/null || true)
        if [ -n "$cand" ] && node_ok "$cand"; then
            node_bin=$cand
        fi
    fi

    if [ -n "$node_bin" ]; then
        log "Using Node.js at $node_bin"
    else
        log "No usable Node.js 24+ found (or forced); downloading Node.js $node_want under $home_dir"
        command -v curl >/dev/null 2>&1 || fail "curl is required to download Node.js"
        case $os in
            Darwin) plat=darwin ;;
            Linux) plat=linux ;;
            *) fail "unsupported OS: $os" ;;
        esac
        case $(uname -m) in
            arm64 | aarch64) arch=arm64 ;;
            x86_64 | amd64) arch=x64 ;;
            *) fail "unsupported CPU: $(uname -m)" ;;
        esac
        name=node-v$node_want-$plat-$arch.tar.gz
        run "download Node.js checksums" curl -fsSL --retry 3 -o "$tmp_dir/SHASUMS256.txt" "$dist_url/v$node_want/SHASUMS256.txt"
        run "download Node.js $node_want" curl -fsSL --retry 3 -o "$tmp_dir/$name" "$dist_url/v$node_want/$name"
        log "fetched: node-runtime $(file_size "$tmp_dir/$name") bytes"
        expected=$(grep " $name\$" "$tmp_dir/SHASUMS256.txt" | cut -d' ' -f1)
        [ -n "$expected" ] || fail "no checksum listed for $name"
        [ "$(sha256_of "$tmp_dir/$name")" = "$expected" ] || fail "checksum mismatch for $name"
        rm -rf "$home_dir/node"
        mkdir -p "$home_dir/node"
        run "unpack Node.js" tar -xzf "$tmp_dir/$name" -C "$home_dir/node" --strip-components=1
        node_bin=$home_dir/node/bin/node
        node_ok "$node_bin" || fail "downloaded Node.js is not usable: $node_bin"
        runtime_downloaded=yes
        log "Installed Node.js at $node_bin"
    fi
    node_dir=$(dirname "$node_bin")

    # ---- 2. install the package ------------------------------------------------
    export PATH="$node_dir:$PATH"
    npm_cache=$home_dir/cache/npm
    case $tarball in
        http://* | https://*)
            command -v curl >/dev/null 2>&1 || fail "curl is required to download the tarball"
            tgz=$tmp_dir/$(basename "$tarball")
            run "download tarball" curl -fsSL --retry 3 -o "$tgz" "$tarball"
            log "fetched: tarball $(file_size "$tgz") bytes"
            tarball=$tgz
            ;;
    esac
    run "npm install $tarball" "$node_dir/npm" install --prefix "$home_dir" --cache "$npm_cache" \
        --no-audit --no-fund --no-progress "$tarball"
    if [ -d "$npm_cache" ]; then
        cache_kb=$(du -sk "$npm_cache" | cut -f1)
        log "fetched: npm downloads about $((cache_kb * 1024)) bytes (npm cache size, cache removed below)"
        rm -rf "$npm_cache"
    fi
    cli=$home_dir/node_modules/benchnotes/bin/benchnotes.js
    [ -f "$cli" ] || fail "npm did not install benchnotes under $home_dir/node_modules"

    # ---- 3. native shell ---------------------------------------------------------
    shell_path=
    skip=
    [ "${BENCHNOTES_SKIP_BACKEND_CHECK:-0}" = 1 ] && skip=--skip-backend
    if [ "$os" = Darwin ]; then
        # shellcheck disable=SC2086
        run "build macOS app" "$node_bin" "$cli" shell build --apps-dir "$apps_dir" $skip
        shell_path=$apps_dir/Bench\ Notes\ \(bshell-node\).app
    else
        log "Not macOS: no native shell is built. Start the app with: $node_bin $cli ui"
    fi

    # ---- 4. self-test ------------------------------------------------------------
    # shellcheck disable=SC2086
    run "self-test" "$node_bin" "$cli" ui --check $skip

    elapsed=$(($(date +%s) - started))
    log "runtime_downloaded: $runtime_downloaded"
    log "install_seconds: $elapsed"
    log "prefix: $home_dir"
    log "interpreter: $node_bin"
    log "cli: $cli"
    log "launch: $node_bin $cli ui"
    [ -n "$shell_path" ] && log "app: $shell_path"
    log "Done."
}

main "$@"
