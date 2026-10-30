# Decisions and trade-offs

Each entry says what was chosen, why, and what it costs. Versions are the ones current when
this was written (late October 2026); the scripts pin them.

## Outcomes of the known risks (R1-R5)

### R1: Tauri and Wails Linux builds need webkit2gtk development libraries

- The libraries were installable here (`libwebkit2gtk-4.1-dev`, `libgtk-3-dev`,
  `libayatana-appindicator3-dev`, `librsvg2-dev`, `libxdo-dev`).
- Tauri: built in release mode on Linux (`sh variants/tauri/build.sh`, about 5.5 minutes),
  its Rust store tests pass, and the binary opened a real window under Xvfb and wrote the
  ready file. Only the Linux build was done; the macOS and Windows Tauri builds are CI-only.
- Wails: the code is written and the Go store tests pass (`go test ./store/...`), but
  the Wails CLI could not be installed in this sandbox: `go install` goes through
  proxy.golang.org, which the sandbox blocks (HTTP 403). I did not try other ways around it.
  The Wails build and its smoke check have therefore never run, on any OS. The first run
  is the CI job, and I expect it to need at least one fix (see verification.md).
- Wails on Linux with Ubuntu 24.04 needs `-tags webkit2_41` because the 4.0 development
  package is gone; the build script sets it. This only matters for the Linux build, which
  is not a benchmark platform.

### R2: Intel macOS hosted runners

- Label used: `macos-15-intel` (x86_64). Apple Silicon: `macos-15`. Windows: `windows-2025`.
- From GitHub's changelog: `macos-13` was retired on December 4, 2025, and GitHub says Intel
  macOS support ends when the macOS 15 image is retired (fall 2027). The `macos-14-large`
  and `macos-15-large` labels are also Intel but are paid larger runners. docs.github.com
  could not be fetched from the sandbox, so the label list comes from the changelog and web
  search, not from the current runner reference page. Check it before relying on it.
- If the label stops working, `scripts/build_all.sh` run on an Intel Mac produces the same
  `dist/macos-x64/`. The build scripts need no CI-specific input.

### R3: the Node web view binding is a native addon

- Chosen: `@webviewjs/webview` 0.4.9 (a napi-rs addon over Rust `wry` / `tao`, the same
  windowing crates Tauri uses). Considered from the npm registry: `webview-nodejs`
  0.5.0 (small, 29 kB unpacked), `webview-node` 0.1.41, `webview-napi` 2.2.0 (68 MB
  unpacked) and `node-webview` (last published 2022). I did not install or run the others;
  the choice rests on registry metadata (recent publish date, per-platform prebuilt packages for
  macOS arm64 / x64, Windows x64 and Linux) and on this one working in this sandbox.
  That is a weaker basis than a head-to-head test and it is the first thing to revisit if the
  binding turns out to be a problem.
- The finding for the paper: any Node binding to a native web view is compiled code from npm.
  It arrives as a `.node` shared library that the operating system may evaluate separately
  (Windows Smart App Control, antivirus, macOS library validation / quarantine on a
  downloaded dylib). The Python variant is not free of native code either: pywebview
  pulls in pyobjc on macOS and pythonnet on Windows, which are compiled packages too. The
  difference is one of degree and of provenance (widely used wheels loaded by a Python
  interpreter that is itself installed per user, against a single prebuilt addon from a
  small project loaded into Node), and I have not measured whether any OS treats the two
  differently. What the repo does is make the dependency visible: `bshell/node/src/webview.js`
  loads the addon in one place and fails with an explicit message, with no fallback to a
  browser.
- Consequence for requirements: this binding's native package declares `node >= 24`, so
  with Node 22 npm silently skips the optional platform package and the window cannot open.
  The package declares `engines.node >= 24`, both installers check for Node 24+, and
  they download a private Node.js 24.22.1 if no suitable Node exists. This makes the
  Node variant's "runtime absent" cost the cost of a Node 24 download, and it excludes a
  user whose only Node is 20 or 22 from reusing it. Found by actually running it on Node 22.
- Linux needs `libxdo` and WebKitGTK 4.1 for this binding. Not relevant on the benchmark
  platforms.

### R4: noisy macOS memory

Addressed in the method rather than hidden: snapshot-difference attribution (not tree
walking), RSS plus USS plus macOS physical footprint, a quiet-machine precheck, one sample at
60 s, the raw per-process list stored in the results file. Remaining noise and failure
modes are listed in method.md. None of this has been run on macOS; the footprint
extraction in particular is untested against real `footprint` output (only its parser is
unit-tested on a sample string).

### R5: fairness

- Default release configuration for every framework (see method.md for the list). The zip
  packaging step is common to all variants, which handicaps none of them.
- The app code is the same; per-variant code is limited to the adapter and the minimum
  backend each framework needs (a store in Rust, Go, Node or JavaScript for the
  native-backend variants). The Electron variant reuses the Node store from the Borrowed
  Shell package; the Tauri and Wails stores are separate implementations of the same
  JSON-file behaviour.
- Toolchain versions: Electron 45.0.0, electron-builder 26.18.0, Tauri CLI 2.12.4 (`tauri`
  2.12.x, `tauri-build` 2.7), Wails v2.17.0, Neutralinojs 6.10.0 with neu CLI 11.8.0,
  pywebview 6.2.1, PyInstaller 6.22.3, hatchling 1.32.4, `@webviewjs/webview` 0.4.9,
  psutil 7.2.2 (harness). Build hosts used here: Python 3.13.17, Node 22.23.4 for the
  Linux builds (24.22.1 for the Node 24 checks), Go 1.24.7, Rust 1.97, uv 0.11.32. Each build
  writes the versions it used into `dist/.../manifest.json`.
- Not equal and cannot be made equal: Electron bundles Chromium, the others use the OS's web
  view, so the "web engine" differs by design; that difference is what is being measured. On
  Windows 10 vs 11 the WebView2 runtime version may differ and the harness does not pin it.

## Design choices

### Server stack for the Python package: standard library only

`ThreadingHTTPServer` from `http.server`, not uvicorn. The server is about 220 lines, has no
dependencies beyond pywebview, and the wheel is 21 kB. Trade-off: no HTTP/2 and no async,
irrelevant for a single-window local app, and the hardening (Host, Origin, token, CSP, static
allow-list) is hand-written, so it is covered by tests rather than inherited from a framework.
The Node server does the same with `node:http` for symmetry.

### API prefix `/rpc/`, not `/api/`

The shared frontend has a directory `frontend/api/` holding the adapters. A real window under
Xvfb showed that gating `/api/*` behind the token also gated `/api/adapter.js`, which the
page must load before it has used its token. Renaming the data endpoints to `/rpc/` fixed it;
regression tests cover both languages. The unit tests had passed before that because they
used a stand-in frontend; the bug was found only by opening a real page.

### Token in the URL fragment, sent as a header

The fragment is never sent to the server and never reaches logs or referrers. The adapter reads it
once and sends `X-Bench-Token` on every `/rpc/` call. Static files are served without a token
because they contain nothing secret and the shell must load them before the token is in use.
Trade-off: the token is visible in the window's URL on platforms where that is shown. No
browser fallback exists, so there is no URL a user could paste elsewhere.

### Node returns 400 where Python returns 403 for malformed Host

`node:http` rejects missing, duplicate or empty `Host` headers before the handler runs (400).
The tests accept 400 or 403 for those cases and require 403 for a wrong but well-formed Host.
Either way the request is refused.

### Ready file written by the backend, triggered by the page

`api.ready()` is called after the first `requestAnimationFrame`. For HTTP variants the server
writes the file on the `/rpc/ready` call. Electron writes it from the main process on IPC.
Tauri and Wails do the same from their command handlers. Neutralino has no backend process, so its
adapter writes the file directly through the Neutralino filesystem API, which makes its timing path slightly
different (page-side write). Recorded, not corrected.

### Neutralino keeps its logic in the page

Neutralino has no default backend language; the "extension" route adds a separate process
and would change the memory profile. The default configuration is page JavaScript plus
the native filesystem API, so that is what the variant does. Its smoke check can only verify
that the zip contains an executable and `resources.neu`; a real launch is covered by the
harness (and was done under Xvfb during development).

### PyInstaller is the "tried and replaced" baseline

It freezes the exact same `benchnotes` wheel and uses the same server and pywebview, in the default
one-directory mode with `--windowed` on macOS and Windows. A one-file build would be smaller
on disk and slower to start; the plan said default configuration, and onedir is
PyInstaller's current default recommendation.

### macOS shell for the Python variant

`Bench Notes (bshell-py).app` contains an Info.plist with its own bundle id,
`Contents/MacOS/launch` (a shell script that logs and execs), a symlink to the real
interpreter Mach-O (resolved through framework stubs, so the process shows up under the app's
own name), `pyvenv.cfg`, and `Contents/lib/site-packages` symlinked into the venv.
`sys.prefix` is computed from the executable location, so the symlink layout had to put
`site-packages` where `sys.prefix/lib/pythonX.Y/site-packages` is searched. A first layout
was wrong and was fixed (verified only by a Linux test of the layout and by running the
interpreter through the same symlink arrangement on Linux). It is built in a staging
directory, self-tested, then swapped into place. Whether macOS accepts an unsigned
bundle assembled this way, whether Gatekeeper treats a symlinked Mach-O as the bundle
executable, and whether WKWebView starts correctly from it are all unverified.

### Windows shell for the Python variant

A Start-menu shortcut to the venv's `pythonw.exe -m benchnotes ui` with its own icon.
`pythonw` has no stdout / stderr, so the app redirects both to a log file before anything else
runs; the WebView2 and .NET 4.7.2 registry keys are checked before pywebview's backend is
imported, and a missing prerequisite produces one actionable sentence.

### Windows shell for the Node variant

`node.exe` is a console program. The shortcut starts it minimised (`WindowStyle = 7`) with
`ui --detach`, and the app re-launches itself hidden and detached so no console window
stays. Trade-off: a console window flashes briefly and the detached process is a second
`node.exe` start, which adds to cold start. Untested on Windows.

### PowerShell installers

ASCII only, no double-quote characters at all in the installers (so arguments to native
programs cannot be mangled by the 5.1 argument-passing rules), everything inside one
function called on the last line (so a truncated download cannot run a partial script),
no PowerShell 7 syntax, exit codes checked after each native call. These are enforced by
`bench/tests/test_install_ps1.py`. Passing those tests does not mean they work on 5.1;
the parser used for the syntax check is PowerShell 7.5.9.

### Installer behaviour that the harness depends on

- Downloads go to a file first and are checked (SHASUMS256 for Node) before use.
- pip / uv / npm caches live inside the private home and are deleted at the end (footprint
  accounting; a user-level cache would otherwise be shared across apps and be hard to attribute).
- Python provisioned by uv defaults to 3.12 (`BENCHNOTES_PYTHON_VERSION`), a conservative pick
  for pywebview's Windows dependency (pythonnet) and macOS pyobjc wheels. Python 3.13 was used
  for development and the wheel is pure Python, so it installs on any 3.11+.

### Harness

- Python 3.11+ with only `psutil`, one driver per OS family. GUI launches go through OS
  commands and the harness polls a file, as the plan accepts, rather than instrumenting each
  framework.
- `xvfb-run` wrapping exists but is opt-in (`BENCH_XVFB=1`) because wrapping every launch
  put the Xvfb process itself into the memory sums.
- On the first launch memory is not sampled; only the second launch is. That keeps the first
  launch short and the idle sample on a warm install, but it means "idle memory" is for the
  second launch.
- The update measurement uses the offline path; the online fallback is not measured.

### Report

- The shape of the paper's Table 7.5 is an assumption, because the paper is not in the repo.
  The default is: one row per variant, columns download (runtime present, absent), disk (first
  app, marginal app), idle memory (RSS sum, and macOS physical footprint), cold start (first,
  later), install time, install success, update cost (bytes, time). `TABLE_75` at the top of
  `bench/report.py` is the one place to change it.
- Without `--table75-platform`, Table 7.5 pools all platforms and says so in an italic note;
  the per-platform tables are the ones to cite.

### Synthetic data

`bench/tests/synthetic.py` makes random numbers with a fixed seed and flags the files
`host.synthetic = true`; the report prints a banner. The numbers describe nothing real; the
generator exists only to exercise the report. Do not quote them.

### Things I chose not to do

- No code signing or notarization (matches the paper's premise).
- No Linux benchmark platform; Linux is a development and test environment.
- No retry or workaround when the sandbox blocked a download (proxy.golang.org,
  nodejs.org, docs.github.com); the limitation is recorded and the affected piece was
  tested with a local stand-in (see verification.md) or left unrun.
