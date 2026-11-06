---
name: borrowed-shell
description: Build or retrofit a desktop app using the Borrowed Shell pattern - a pure Python or Node.js package that serves its UI on 127.0.0.1, shows it in the OS web view (WKWebView/WebView2), and is installed by a one-line curl/irm script that assembles a native .app bundle or Start-menu shortcut on the user's machine, so nothing the vendor compiles needs signing. Use when asked to ship a web-UI tool as a desktop app without Electron, without code signing, or "the Borrowed Shell way".
---

# Borrowed Shell

Ship a desktop app as a pure-language package. Borrow everything else from the machine:

- **Window:** the system web view (WKWebView on macOS, WebView2 on Windows) via pywebview or a Node binding.
- **Runtime:** the user's Python 3.11+ / Node.js 24+, or a per-user one the installer fetches (no admin).
- **Identity:** a `.app` bundle (macOS) or `.lnk` (Windows) that the installer builds locally, so it never carries the quarantine attribute and Gatekeeper first-launch approval never applies.

The one rule that keeps the pattern intact: **the download contains nothing compiled by the vendor.** A compiled launcher, a prebuilt `.app` or a frozen executable brings code signing back. Third-party native extensions (pyobjc, pythonnet, `@webviewjs/webview`) are judged on their own signatures - say so to the user, don't hide it.

Paper: "The Borrowed Shell Pattern" (A. Chatterjee, Gritsa Ltd, 2026). Reference implementation: https://github.com/abi-chatterjee/borrowed-shell-bench (`bshell/py`, `bshell/node`), DOI 10.5281/zenodo.23954439.

## 0. Check fit before writing code

Proceed only if most are true; otherwise tell the user why and stop:

1. The UI can be a web page served from localhost.
2. Users can paste one terminal command on machines they control.
3. The app needs no vendor-compiled code (no custom native module of your own).
4. Readable source is acceptable (a pure wheel/npm package is readable; protecting it later multiplies builds per OS/CPU/runtime).
5. Not required: app-store distribution, MDM-managed fleets, tray icon, start-at-login, pixel-identical rendering across OSes.

Pick the runtime the app is already written in. Python: pywebview. Node.js: `@webviewjs/webview` (napi-rs addon; its platform packages need Node >= 24 and npm skips them **silently** on older Node).

## 1. Build in this order (each step has a reference file)

| Step | What | Read |
|---|---|---|
| 1 | Self-test command (`<app> ui --check`) first | below |
| 2 | Loopback server + window on main thread, logging | `references/runtime.md` |
| 3 | Windows preflight (WebView2, .NET 4.7.2) before importing the backend | `references/runtime.md` |
| 4 | macOS `.app` shell: symlink to real interpreter + launcher, staged build | `references/macos-shell.md` |
| 5 | Windows Start-menu shortcut | `references/windows-shell.md` |
| 6 | Installers `install.sh` / `install.ps1` | `references/installer.md` |
| 7 | Update and uninstall | `references/installer.md` |

Do not start step 4+ until steps 1-3 pass on the dev machine.

### The self-test (step 1)

One command used by CI, support, the installer and the bundle builder. It must:

1. Start the server on a free port with a throwaway data dir.
2. Fetch `/` and check for a known string; check an API route returns 403 without the token and 200 with it.
3. Import the **native window backend** (not just the wrapper library) and fail if it is missing. Offer `--skip-backend` for headless CI only.
4. Exit non-zero with one readable line on any failure.

Python backends to import: `webview.platforms.cocoa` (macOS), `webview.platforms.edgechromium` (Windows). Node: `require('@webviewjs/webview')` inside try/catch.

## 2. Hard rules (each one is a bug someone already hit)

- **No silent browser fallback.** Force the GUI (`webview.start(gui='cocoa'|'edgechromium')`). Without WebView2, pywebview on Windows silently drops to the IE engine and the window opens blank. A missing backend is an error with an actionable sentence.
- **Window on the main thread, server on a daemon thread.** Cocoa requires it. Wait until the socket accepts connections before opening the window.
- **Harden the loopback server:** bind `127.0.0.1` port 0; require `Host` == `127.0.0.1:<port>` exactly; if `Origin` is present it must equal `http://127.0.0.1:<port>`; per-launch random token passed to the page in the URL **fragment** (`/#token=...`, never a query string) and sent back as a header, compared in constant time; mutating requests also require `Origin` and `Content-Type: application/json`; static files from an allow-list; send CSP `default-src 'self'`.
- **Windowless processes have no stdout.** `pythonw` sets `sys.stdout`/`sys.stderr` to `None`; redirect both to a log file on the first line of `main()`. On macOS the launcher script redirects to `~/Library/Logs/<App>/`.
- **Dock name/icon come only from a bundle containing the real executable.** On framework Pythons `bin/python3` is a stub that re-execs `Python.app`; symlink the inner Mach-O, not the stub. Verify by launching the bundle, never by importing.
- **Windows taskbar icon:** pass the icon to the window (`webview.start(icon=...)`; Node: `windowsTaskbarIcon` + `setWindowIcon`), or the taskbar shows python/node's icon.
- **ATS:** Info.plist needs `NSAppTransportSecurity > NSAllowsLocalNetworking = true` or WKWebView refuses `http://127.0.0.1`.
- **Borrow tools from the chosen runtime, not PATH.** The updater must call the `npm`/`pip` beside the running interpreter (`path.dirname(process.execPath)`, `sys.executable -m pip`); a PATH `npm` from an older system Node installs then fails.
- **Installers:** everything inside `main()` called on the last line (a truncated `curl | sh` runs nothing); download any sub-installer (uv, Node) to a file before running it; never `sudo`/admin; log every step; all locations overridable by env vars; PowerShell files ASCII-only, PS 5.1 compatible, no double-quote characters.
- **Staged shell builds:** build in a hidden staging dir, run the self-test through the shell, then swap. Refuse to replace an existing bundle whose `CFBundleIdentifier` differs.
- **Never claim a platform works unless it was run there.** Record what was run, where, and what was not.

## 3. Deliverables checklist

- [ ] `<app> ui` (window), `<app> ui --check [--skip-backend]`, `<app> update --wheel|--tarball <path>`, `<app> shell build` (macOS)
- [ ] Loopback server with Host/Origin/token/content-type guards and tests proving each refusal (wrong Host, foreign Origin, missing token -> 403)
- [ ] Windows preflight with registry checks and a native message box (pythonw has no console)
- [ ] macOS shell builder (Info.plist with own bundle id, launcher, interpreter symlink, Python: `pyvenv.cfg` + `site-packages` symlink), staged + self-tested
- [ ] Windows `.lnk` to `pythonw.exe -m <pkg> ui` (Node: `node.exe` minimised, app relaunches itself detached), own `.ico`, verified after creation
- [ ] `install.sh` + `install.ps1` (+ optional `install.cmd` wrapper for zip delivery)
- [ ] Uninstall instructions or script (shell, private env, per-user runtime if added and unused; keep user data unless asked)
- [ ] A verification note listing each platform path as run / written-not-run

## 4. Verification you must actually do

- macOS: run the installer with `<APP>_HOME`/`<APP>_APPS_DIR` pointed at scratch dirs; `open` the bundle; `lsappinfo info -only name,bundleID "<App Name>"` shows your name and bundle id; Dock icon is yours; `xattr -l` on the bundle shows no `com.apple.quarantine`.
- Windows: run `install.ps1` from `irm | iex` and from a downloaded zip; shortcut launches with no console; taskbar icon is yours; self-test passes through `pythonw` too.
- Update: install v1, update from a local package offline, relaunch, confirm the version string; on macOS confirm the bundle still launches.
- If you cannot run a platform, say so explicitly in your summary.

## 5. Tech debt to declare to the user

- Readable source; code protection later turns one package into an OS x CPU x runtime build matrix.
- The static host and installer are the root of trust: publish checksums, pin versions, scan every artifact before publishing (everything on the host is public, and caches may serve the previous release for minutes).
- Updating files while the app runs on Windows (pythonw + .NET bridge) is untested in the reference implementation.
- Smart App Control and MDM/App Control policies are untested; native extensions may be blocked there.
