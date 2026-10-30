#!/bin/sh
# Bench Notes (bshell-py) installer for macOS (and Linux, without the shell step).
#
#   curl -fsSL <url>/install.sh | sh
#
# What it does, per user, never with sudo:
#   1. find Python 3.11+ (or install a private one with uv)
#   2. create a private venv under $BENCHNOTES_HOME
#   3. pip install the benchnotes wheel (and pywebview) into it
#   4. macOS: build "Bench Notes (bshell-py).app" in $BENCHNOTES_APPS_DIR
#   5. run the self-test (benchnotes ui --check)
#
# Environment overrides (all optional):
#   BENCHNOTES_HOME                  install root                (default ~/.benchnotes)
#   BENCHNOTES_APPS_DIR              where the .app goes         (default ~/Applications)
#   BENCHNOTES_WHEEL                 local wheel path or URL     (default: "benchnotes" from the package index)
#   BENCHNOTES_PYTHON_VERSION        Python installed by uv      (default 3.12)
#   BENCHNOTES_FORCE_RUNTIME_INSTALL 1 = ignore any Python found, install one (used to measure "runtime absent")
#   BENCHNOTES_UV_INSTALLER_URL      uv installer location       (default https://astral.sh/uv/install.sh)
#   BENCHNOTES_SKIP_BACKEND_CHECK    1 = self-test without a window backend (CI/Linux only)
#
# Everything lives inside main(), called on the last line, so a truncated
# download cannot run half a script.

main() {
    set -eu

    home_dir=${BENCHNOTES_HOME:-$HOME/.benchnotes}
    apps_dir=${BENCHNOTES_APPS_DIR:-$HOME/Applications}
    wheel=${BENCHNOTES_WHEEL:-benchnotes}
    py_want=${BENCHNOTES_PYTHON_VERSION:-3.12}
    force_runtime=${BENCHNOTES_FORCE_RUNTIME_INSTALL:-0}
    uv_url=${BENCHNOTES_UV_INSTALLER_URL:-https://astral.sh/uv/install.sh}
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

    # Run a command with its output going to the log; fail with a message.
    run() {
        what=$1
        shift
        log "-> $what"
        if ! "$@" >>"$log_file" 2>&1; then
            fail "$what failed"
        fi
    }

    file_size() { wc -c <"$1" | tr -d ' '; }

    # ---- 1. Python ---------------------------------------------------------
    python_ok() {
        # usable = 3.11+, has venv and ensurepip (Debian splits these out)
        "$1" -c 'import sys,venv,ensurepip; sys.exit(0 if sys.version_info>=(3,11) else 1)' >/dev/null 2>&1
    }

    find_python() {
        for name in python3.13 python3.12 python3.11 python3 python; do
            cand=$(command -v "$name" 2>/dev/null || true)
            [ -n "$cand" ] || continue
            # /usr/bin/python3 on a Mac without the Command Line Tools is a stub
            # that pops up an install dialog when run. Never run it blindly.
            if [ "$os" = Darwin ] && [ "$cand" = /usr/bin/python3 ] && ! xcode-select -p >/dev/null 2>&1; then
                continue
            fi
            if python_ok "$cand"; then
                printf '%s\n' "$cand"
                return 0
            fi
        done
        return 1
    }

    python_bin=
    runtime_downloaded=no
    if [ "$force_runtime" != 1 ]; then
        python_bin=$(find_python || true)
    fi

    if [ -n "$python_bin" ]; then
        log "Using Python at $python_bin"
    else
        log "No usable Python 3.11+ found (or forced); installing Python $py_want with uv under $home_dir"
        command -v curl >/dev/null 2>&1 || fail "curl is required to download uv"
        uv_dir=$home_dir/uv
        installer=$tmp_dir/uv-installer.sh
        # Download to a file first, so a dropped connection cannot execute half a script.
        run "download uv installer" curl -fsSL --retry 3 -o "$installer" "$uv_url"
        log "fetched: uv-installer $(file_size "$installer") bytes"
        # Both variables: UNMANAGED = no PATH edits, no receipt; NO_MODIFY_PATH for older installers.
        run "run uv installer" env UV_UNMANAGED_INSTALL="$uv_dir" UV_INSTALL_DIR="$uv_dir" \
            UV_NO_MODIFY_PATH=1 sh "$installer"
        uv_bin=
        for cand in "$uv_dir/uv" "$uv_dir/bin/uv"; do
            [ -x "$cand" ] && uv_bin=$cand && break
        done
        [ -n "$uv_bin" ] || fail "uv installer did not produce a uv binary under $uv_dir"
        export UV_PYTHON_INSTALL_DIR="$home_dir/python"
        export UV_CACHE_DIR="$home_dir/cache/uv"
        export UV_PYTHON_INSTALL_BIN=0
        export UV_PYTHON_INSTALL_REGISTRY=0
        run "install Python $py_want" "$uv_bin" python install "$py_want"
        python_bin=$("$uv_bin" python find "$py_want" 2>>"$log_file") || fail "uv could not find the Python it just installed"
        python_ok "$python_bin" || fail "Python installed by uv is not usable: $python_bin"
        runtime_downloaded=yes
        log "Installed Python at $python_bin"
    fi

    # ---- 2. private venv ---------------------------------------------------
    venv=$home_dir/venv
    run "create venv" "$python_bin" -m venv --clear "$venv"
    venv_py=$venv/bin/python

    # ---- 3. install the package -------------------------------------------
    export PIP_CACHE_DIR="$home_dir/cache/pip"
    export PIP_DISABLE_PIP_VERSION_CHECK=1
    export PIP_NO_INPUT=1
    case $wheel in
        http://* | https://*)
            command -v curl >/dev/null 2>&1 || fail "curl is required to download the wheel"
            wheel_file=$tmp_dir/$(basename "$wheel")
            run "download wheel" curl -fsSL --retry 3 -o "$wheel_file" "$wheel"
            log "fetched: wheel $(file_size "$wheel_file") bytes"
            wheel=$wheel_file
            ;;
    esac
    run "pip install $wheel" "$venv_py" -m pip install "$wheel"
    if [ -d "$PIP_CACHE_DIR" ]; then
        cache_kb=$(du -sk "$PIP_CACHE_DIR" | cut -f1)
        log "fetched: pip downloads about $((cache_kb * 1024)) bytes (pip cache size, cache removed below)"
        rm -rf "$PIP_CACHE_DIR"
    fi
    rm -rf "$home_dir/cache/uv"

    # ---- 4. native shell ---------------------------------------------------
    shell_path=
    if [ "$os" = Darwin ]; then
        if [ "${BENCHNOTES_SKIP_BACKEND_CHECK:-0}" = 1 ]; then
            run "build macOS app" "$venv_py" -m benchnotes shell build --apps-dir "$apps_dir" --skip-backend
        else
            run "build macOS app" "$venv_py" -m benchnotes shell build --apps-dir "$apps_dir"
        fi
        shell_path=$apps_dir/Bench\ Notes\ \(bshell-py\).app
    else
        log "Not macOS: no native shell is built. Start the app with: $venv_py -m benchnotes ui"
    fi

    # ---- 5. self-test ------------------------------------------------------
    if [ "${BENCHNOTES_SKIP_BACKEND_CHECK:-0}" = 1 ]; then
        run "self-test (backend skipped)" "$venv_py" -m benchnotes ui --check --skip-backend
    else
        run "self-test" "$venv_py" -m benchnotes ui --check
    fi

    elapsed=$(($(date +%s) - started))
    log "runtime_downloaded: $runtime_downloaded"
    log "install_seconds: $elapsed"
    log "venv: $venv"
    log "interpreter: $venv_py"
    log "launch: $venv_py -m benchnotes ui"
    [ -n "$shell_path" ] && log "app: $shell_path"
    log "Done."
}

main "$@"
