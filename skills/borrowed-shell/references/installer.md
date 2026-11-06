# Installer, update, uninstall

Users run one line:

```sh
curl -fsSL https://<static-host>/install.sh | sh          # macOS / Linux
```
```powershell
irm https://<static-host>/install.ps1 | iex                # Windows PowerShell 5.1+
```

Optional zip route: the same scripts plus the package file in a zip; on Windows an `install.cmd` runs `powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1` so a downloaded script is not refused and no system setting changes.

## Sequence (both scripts)

1. **Find a runtime**, or install a private one per user.
   - Python: try `python3.13 python3.12 python3.11 python3 python` (Windows: `py -3.13/-3.12/-3.11`, `python`, `python3`). Usable = `>=3.11` and `import venv, ensurepip` succeeds (Debian splits these out).
     - macOS: skip `/usr/bin/python3` when `xcode-select -p` fails; it is a stub that pops an install dialog.
     - Windows: reject paths under `\WindowsApps\` (Microsoft Store Python misbehaves in venvs).
     - None usable: download the uv installer **to a file**, run it with `UV_UNMANAGED_INSTALL=<home>/uv UV_INSTALL_DIR=<home>/uv UV_NO_MODIFY_PATH=1`, then `uv python install 3.12` with `UV_PYTHON_INSTALL_DIR=<home>/python UV_PYTHON_INSTALL_BIN=0 UV_PYTHON_INSTALL_REGISTRY=0`, then `uv python find 3.12`.
   - Node: accept `node` >= 24 with `npm` beside it; otherwise download the official build from nodejs.org/dist for the OS/arch, **verify it against `SHASUMS256.txt`**, unpack under `<home>/node`.
   - Prefer official, publisher-signed runtimes where Smart App Control or similar may apply.
2. **Private environment**: `python -m venv --clear <home>/venv` / `npm install --prefix <home>/app`.
3. **Install the package** (local path or URL; download URLs to a file first). Python: `<venv>/bin/python -m pip install <wheel>`.
4. **Build the shell**: macOS `.app` (`<pkg> shell build`, staged + self-tested); Windows `.lnk`; Linux: print the launch command (or write a `.desktop` file).
5. **Self-test**: `<pkg> ui --check` (Windows: also through `pythonw`).
6. **Log** every step to `<home>/logs/install.log`; on failure print the last ~15 lines and the log path.

## Shell skeleton (POSIX sh, not bash)

```sh
#!/bin/sh
# <App Name> installer.  curl -fsSL <url>/install.sh | sh
main() {
    set -eu
    home_dir=${<APP>_HOME:-$HOME/.<app>}
    apps_dir=${<APP>_APPS_DIR:-$HOME/Applications}
    pkg=${<APP>_WHEEL:-<pkg>}
    mkdir -p "$home_dir/logs"; log_file=$home_dir/logs/install.log; : >"$log_file"
    tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/<app>-install.XXXXXX")
    log()  { printf '%s\n' "$*" | tee -a "$log_file"; }
    fail() { log "ERROR: $*"; log "Details are in $log_file"; exit 1; }
    cleanup() { s=$?; rm -rf "$tmp_dir"; [ "$s" -eq 0 ] || { echo "Install failed (exit $s). Last log lines:" >&2; tail -n 15 "$log_file" >&2 || true; }; }
    trap cleanup EXIT
    run() { what=$1; shift; log "-> $what"; "$@" >>"$log_file" 2>&1 || fail "$what failed"; }
    # 1 runtime, 2 venv, 3 pip install, 4 shell, 5 self-test (see above)
    log "Done."
}
main "$@"
```

Under `curl | sh` stdin is the script itself: any interactive prompt must read from `/dev/tty`, and fall back to no prompts when there is no terminal, `NO_COLOR` is set or `TERM=dumb`.

## PowerShell rules (Windows PowerShell 5.1)

- ASCII only (5.1 reads BOM-less files as ANSI).
- **No double-quote characters anywhere**: 5.1 mangles embedded quotes in arguments to native programs. Single-quote every string; build arguments as arrays.
- Everything inside one function called on the last line.
- `$ErrorActionPreference = 'Stop'`; `$ProgressPreference = 'SilentlyContinue'` (Invoke-WebRequest is much slower with a progress bar); enable TLS 1.2 explicitly.
- Wrap native calls: set `$ErrorActionPreference = 'Continue'` around `& $exe @args 2>&1`, append output to the log, then check `$LASTEXITCODE`.
- Add a test that fails the build if `install.ps1` contains a non-ASCII byte or a `"`.

## Environment switches (document all of them at the top of each script)

`<APP>_HOME`, `<APP>_APPS_DIR`, `<APP>_WHEEL` / `<APP>_TARBALL` (local path or URL), `<APP>_PYTHON_VERSION` / `<APP>_NODE_VERSION`, `<APP>_UV_INSTALLER_URL` / `<APP>_NODE_DIST_URL` (mirrors behind firewalls), `<APP>_FORCE_RUNTIME_INSTALL=1`, `<APP>_SKIP_BACKEND_CHECK=1` (CI only). These let a trial install never touch a real one.

## Update

Both shells point at the private environment, so swapping the package updates the app.

```python
PIP = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--quiet"]
r = run(PIP + ["--no-index", "--upgrade", wheel])        # offline first: costs only the wheel (tens of KB)
if r.returncode != 0:
    r = run(PIP + ["--upgrade", wheel])                  # a release that adds a dependency needs the index
```

Node: `npm install --offline --no-audit --no-fund --prefix <prefix> <tarball>`, then online fallback, using the **npm beside `process.execPath`** (`npm.cmd` on Windows), never the PATH one.

Rebuild the macOS shell only when the shell itself changed (icon, Info.plist, launcher) or the interpreter moved; a version-stamped Info.plist means rebuilding on every update - choose and document.

Left to the implementation (state which you chose): how the app learns of a new version (e.g. `latest.json` on the static host) and how it verifies the package (published SHA-256 checked before install).

## Uninstall

Remove, in order: the shell (`~/Applications/<App Name>.app` or the `.lnk`), the private environment (`<home>/venv` or `<home>/app`), the per-user runtime only if this installer added it and nothing else uses it. Keep user data (database, logs) unless the user explicitly asks; print where it is.

## Distribution host

A static host (GitHub Pages etc.) is enough; no vendor server. Everything on it is public and cached (GitHub Pages: ~10 minutes, including 404s), so users may get the previous installer just after a release. Publish checksums, pin versions, and scan artifacts for secrets and real names before publishing.
