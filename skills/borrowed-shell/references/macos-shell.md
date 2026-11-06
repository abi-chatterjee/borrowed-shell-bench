# macOS shell: a locally assembled .app

Goal: Dock label, menu-bar title, app switcher entry and icon all say `<App Name>`, not "Python" / "node". macOS takes these from the bundle that contains the **process's executable**, so the real interpreter binary must appear to live inside the bundle.

## Layout (all symlinks and small text files, ~10 KB)

```
~/Applications/<App Name>.app/Contents/
  Info.plist                            own CFBundleIdentifier and name
  MacOS/launch                          sh script: log redirect, exec the symlink (CFBundleExecutable)
  MacOS/<Exe> -> <real interpreter Mach-O>
  MacOS/pyvenv.cfg                      Python only: turns the symlinked interpreter into a venv
  lib/pythonX.Y/site-packages -> <private venv>/lib/pythonX.Y/site-packages   (Python only)
  Resources/icon.icns
```

Why each piece:

- **Launcher script as `CFBundleExecutable`**: a symlink cannot carry arguments (`-m <pkg> ui`), and Finder-launched apps have no terminal, so the script redirects output to `~/Library/Logs/<App>/`.
- **Symlink to the real binary**: on framework Pythons (python.org, Homebrew) `bin/python3.X` is a stub that re-execs `Resources/Python.app/Contents/MacOS/Python`, which hands the process back to Python's own bundle. Resolve the inner binary:
  ```python
  fw = sysconfig.get_config_var("PYTHONFRAMEWORK")
  inner = Path(sys.base_prefix) / "Resources" / "Python.app" / "Contents" / "MacOS" / fw
  real = inner if fw and inner.exists() else Path(os.path.realpath(sys._base_executable))
  ```
  Standalone builds (uv / python-build-standalone) have no stub. Node: `fs.realpathSync(process.execPath)`.
- **pyvenv.cfg + site-packages symlink** (Python): CPython sets `sys.prefix` to the parent of the directory holding the executable and its `pyvenv.cfg`, i.e. `Contents/`, so `Contents/lib/pythonX.Y/site-packages` must point at the private venv. A new wheel version then updates the app with no rebuild.
  ```
  home = <dir of real interpreter>
  include-system-site-packages = false
  version = X.Y.Z
  executable = <real interpreter>
  ```
  Prefer a stable `home` (Homebrew: `/opt/homebrew/opt/python@X.Y/...` rather than a versioned `Cellar` path) so interpreter upgrades do not strand the bundle; if you resolve the real path instead, an interpreter upgrade needs a shell rebuild - document that.
- Node needs no `pyvenv.cfg`; the launcher passes the absolute path of the package's `bin/<pkg>.js`.

## Info.plist

```python
{
  "CFBundleName": "<App Name>", "CFBundleDisplayName": "<App Name>",
  "CFBundleIdentifier": "com.<org>.<app>",
  "CFBundleVersion": version, "CFBundleShortVersionString": version,
  "CFBundleExecutable": "launch", "CFBundleIconFile": "icon",
  "CFBundlePackageType": "APPL", "CFBundleInfoDictionaryVersion": "6.0",
  "LSMinimumSystemVersion": "11.0", "NSHighResolutionCapable": True,
  "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},   # WKWebView must load http://127.0.0.1
}
```

When reading plists back in tests, use `plistlib.loads(data, fmt=plistlib.FMT_XML)` as a fallback: a file starting with `<!DOCTYPE` can defeat format detection.

## Launcher

```sh
#!/bin/sh
here=$(cd "$(dirname "$0")" && pwd)
log_dir="${<APP>_LOG_DIR:-$HOME/Library/Logs/<App>}"
mkdir -p "$log_dir"
exec "$here/<Exe>" -m <pkg> ui "$@" >>"$log_dir/<app>.log" 2>&1
```

(Rotate or truncate the log on start if it may grow; the reference appends.)

## Staged build

```python
def build(apps_dir, venv):
    final   = apps / f"{APP_NAME}.app"
    staging = apps / f".{APP_NAME}.app.staging"
    if final.exists() and read_bundle_id(final) != BUNDLE_ID:
        raise RuntimeError(f"{final} belongs to another app; not replacing it")
    shutil.rmtree(staging, ignore_errors=True)
    try:
        assemble(staging, venv)
        self_test(staging)          # run Contents/MacOS/launch --check with <APP>_LOG_DIR in a temp dir; show log tail on failure
        old = None
        if final.exists():
            old = apps / f".{APP_NAME}.app.old-{int(time.time())}"
            os.rename(final, old)
        os.rename(staging, final)
        if old: shutil.rmtree(old, ignore_errors=True)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
```

The bundle-id check above is an improvement over the reference implementation, which does not yet do it.

## Verify identity (by launching, not importing)

```sh
open -n "$HOME/Applications/<App Name>.app"
sleep 3
lsappinfo info -only name,bundleID "<App Name>"      # expect your name and bundle id
xattr -l "$HOME/Applications/<App Name>.app"         # expect no com.apple.quarantine
```

Never bundle a compiled launcher (e.g. a small C/Swift stub) to "fix" identity: it is vendor-compiled code and needs signing and notarisation.
