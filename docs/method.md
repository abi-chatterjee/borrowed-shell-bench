# Measurement method and its known noise

This describes what `bench/run.py` does and what each number does and does not mean. Nothing
below was validated on macOS or Windows yet (see verification.md).

## What is held constant

- The app is the same in every variant. `scripts/check_frontend.py --all` stages the
  frontend for each variant and requires the sha256 of all non-adapter files to be identical.
  The only per-variant frontend file is `frontend/api/<transport>.js`.
- Each framework is built with its default release configuration (`tauri build`,
  `wails build`, `electron-builder` defaults, `neu build`, PyInstaller one-directory mode,
  `--windowed` on macOS and Windows). No size tuning, no stripping, no UPX, no asar changes.
  Toolchain versions are recorded in each `dist/.../manifest.json` and in the results file.
- Data is isolated per run through `BENCH_DATA_DIR`; readiness is signalled through
  `BENCH_READY_FILE`. The page calls `api.ready()` after the first
  `requestAnimationFrame` that follows `DOMContentLoaded`, i.e. after first render.

## Machine preparation

Idle memory and cold start are sensitive to everything else on the machine. Before a run:
restart, close all other applications, disable sleep and notifications, stay plugged in, do
not touch the machine. `run.py` samples total CPU for 5 seconds and refuses to start
when it is above 15% (exit code 3); `--no-quiet-check` overrides this and the results
file then says nothing about it, so write it down yourself.

Record, outside the harness: whether the machine is a laptop, the power mode, whether
Spotlight indexing / Windows Defender scans were running, and whether the first run of a
fresh unsigned download triggered Gatekeeper or SmartScreen prompts. The harness does not
click through such prompts; a prompt makes that run fail on the 60 s timeout and it is
counted in install success.

## Per variant, per run

One run is: install, first launch, quit, second launch, 60 s idle, memory snapshot, quit,
verify nothing is left, then update. Each run starts from an empty scratch directory.

### Install time and install success

- Zip variants (Electron, Tauri, Wails, Neutralino, PyInstaller): "install" is extracting the
  zip into the scratch directory. This is not what a user does with an installer program and
  the number is small. It is reported for uniformity; do not compare it with the Borrowed
  Shell install time as if both were installers.
- Borrowed Shell variants: "install" is the wall-clock time of `install.sh` / `install.ps1`
  from start to exit, including finding or provisioning the runtime when it is missing,
  creating the private environment, installing the package, building the shell, and the
  installer's own `ui --check`. Network speed is part of this number.
- Install success for a run means: the installer (or extraction) succeeded AND the first launch
  wrote a ready file within `--ready-timeout` (60 s). A run where the app starts but never
  renders fails.

### Download size

- Zip variants: size of the zip in `dist/`. It is a zip produced by `scripts/package_zip.py`
  (deflate level 6), not a platform installer (no dmg, msi or nsis). Real distribution
  formats compress differently; this keeps every variant on the same footing.
- Borrowed Shell, runtime present: size of the installer script plus the wheel or tarball,
  plus the bytes of dependency downloads. The installers log lines of the form
  `fetched: <what> <n> bytes`, which `variants.parse_install_log` reads. Dependency bytes
  (pywebview and its platform packages for Python, the native web view addon for Node) are
  an approximation: the installer points pip / npm at a cache inside its private home, sums
  the size of that cache after the install (it contains exactly what this install
  downloaded) and then deletes it. Cached wheels are compressed archives, so this is close to
  the bytes on the wire but not identical (HTTP overhead and metadata requests are not counted).
- Borrowed Shell, runtime absent: script + package + everything the installer downloaded,
  taken from the network interface byte counter (`net_recv_bytes`) over the whole install.
  The "absent" pass sets `BENCHNOTES_FORCE_RUNTIME_INSTALL=1` so the installer provisions its
  own Python (uv, then a standalone CPython build) or Node.js even though one exists. It is a
  forced pass on a machine that has a runtime; the harness cannot make a runtime vanish from
  a real user machine. The installer log cannot be used here: it records the size of the uv
  installer script and of the Node archive, but not of the uv binary or the Python build that
  uv fetches (uv does not keep the archive in its cache; checked on Linux with uv 0.11.32).
  The interface counter sees everything but also any other traffic on the machine during the
  install, so this is the noisiest download number: it is an upper bound, and it is recorded
  once per variant by default (`--absent-runs`), so it has no spread.
- `net_recv_bytes` is also recorded for every ordinary install as a cross-check on the
  logged dependency bytes.

### Disk footprint

- First app: bytes on disk of the private home (runtime, environment, packages, logs) plus
  the shell (.app or shortcut) after a runtime-absent install. For zip variants it is the
  extracted tree.
- Marginal app: after the first app is installed, a second Borrowed Shell app is installed
  with the first app's runtime on PATH. Its disk footprint (its own home plus its shell) is the
  marginal cost of one more app sharing the interpreter. For zip variants marginal equals
  first, because nothing is shared.
- Both apparent size (sum of file sizes) and allocated size (st_blocks, POSIX only) are
  recorded; the table uses apparent size. Symlinks are counted as links and never followed,
  so a symlinked interpreter in the macOS shell is not double counted. On Windows, allocated
  equals apparent. Hard links and macOS APFS clones are not detected, which can make a
  tree look larger than the space it consumes.
- The installers keep pip / uv / npm caches inside their private home and delete them at the
  end, so no cache is left to count. A user who ran plain `pip install` would keep a
  cache; the installers deliberately do not (decisions.md).

### Cold start

- Time from the call that launches the app to the epoch milliseconds in the ready file.
- Launch is done the way a user would: `open -n <app>` for a macOS bundle, running the
  exe or the Start-menu shortcut on Windows. Because `open` and shortcuts cannot carry
  environment variables, on macOS the harness sets `BENCH_READY_FILE` and `BENCH_DATA_DIR`
  with `launchctl setenv` in the user's session for the duration of the launch and removes
  them afterwards. On Windows the harness sets them in its own environment before
  starting the process.
- "First launch" is the first start after install (cold file cache for the new files,
  Gatekeeper / SmartScreen checks if they happen, WebView2 or WKWebView first-use setup).
  "Later launch" is the second start in the same run. The operating system file cache is
  not flushed between runs, so "cold" means "first launch of this install", not "cold disk".
- The clock is the wall clock (epoch ms) in both the harness and the app (the app writes
  `Date.now()` / `time.time()`), so clock skew is zero on one machine. Resolution is about
  20 ms (the harness polls every 20 ms; the ready file write itself is immediate).
- What is included: process start, framework start, window creation, loading the page,
  first render. For the Borrowed Shell this also includes starting the interpreter,
  importing the package and starting the loopback server.
- What is not included: anything after first render, and time before the launch call (for
  example Gatekeeper's assessment of a downloaded app before `open` returns is partly
  inside, partly outside the window depending on the OS).

### Idle memory

- Procedure: snapshot every process (pid + create time) before the second launch; launch;
  wait for the ready file; wait `--idle-seconds` (60) more; then take every process that did
  not exist in the snapshot, sum their resident set size (RSS) and unique set size (USS);
  on macOS also sum physical footprint where it can be read.
- Why not walk the process tree: on macOS, WKWebView content, networking and GPU processes
  are XPC services whose parent is launchd, not the app. A tree walk would silently drop most
  of a system-web-view app and make it look far cheaper than it is. The snapshot difference
  catches them, at the price below.
- Noise and failure modes, stated plainly:
  - Any unrelated process that starts during the 60 s (Spotlight workers, updaters, Defender,
    the harness's own children) is attributed to the app. The quiet check reduces but cannot
    remove this. Read the per-process list stored in the results file (`idle_processes`) when a
    number looks wrong.
  - Shared memory is counted once per process in RSS, so RSS sums overstate. Frameworks
    differ in how much they share (Chromium's zygote on Linux, shared system frameworks on
    macOS). USS (private only) understates. Both are recorded. Which one the paper should
    quote is an editorial decision; the table prints RSS and, on macOS, physical footprint.
  - macOS physical footprint (from `footprint` / `vmmap`, when permitted) is closer to what
    Activity Monitor shows as "Memory" but needs permission to inspect other processes. Where
    it cannot be read the column is empty, not zero.
  - On macOS, shared system web view processes may already be running before the launch
    (if another app uses them) and would then not be counted. This under-attributes in that
    case. Start from a state with no web-view-using application running, as the machine
    preparation says.
  - Memory compression on macOS and Windows working-set trimming change RSS between samples.
    One sample at 60 s is taken, not an average.
  - Windows: the web view runs as several `msedgewebview2.exe` processes launched by the
    WebView2 runtime; they are new processes and are counted. Electron's processes are all
    children of the app and are counted by the same rule.

### Update cost

- Borrowed Shell: after the run, the harness runs the package's own update command with the
  v1.0.1 artifact (`benchnotes update --wheel <path>` or the npm equivalent) in the installed
  environment, and checks that the installed version printed afterwards is 1.0.1. Bytes
  are the update artifact size (the offline update path), time is the command's wall clock.
  The online fallback is not measured.
- Zip variants: the default configuration of these frameworks has no delta updater. The update
  is modelled as downloading the full new zip and replacing the installed copy. Reported
  bytes are the full artifact size and reported time is only the extraction time; the
  download time is not measured (it depends on the network). The result is labelled
  `full-replace` in the results file. Electron's auto-updater, Tauri's updater plugin and
  Wails/Neutralino update mechanisms are optional components and are not part of the
  default configuration, so they are not used.

### Cleanup check

After each launch the harness terminates every process that is new since the snapshot,
waits 0.5 s, and counts survivors (`leftover_procs`). A non-zero count is reported in the
results and indicates the app left a process behind or the harness could not stop it.

## Statistics

`bench/report.py` reports the median and interquartile range (Q1-Q3, linear interpolation)
of the per-run values, per variant, per platform. A single value (one-off measurements such as
the runtime-absent pass, which is run once by default) is printed without a range. With
10 runs the IQR is a rough indicator, not a confidence interval. Runs that failed are
excluded from timing and memory statistics and counted in install success.

The runs of one variant are executed back to back, not interleaved with other variants.
Slow drift (thermal throttling, background indexing) can therefore bias one variant more
than another. Re-running with a different variant order is the cheapest check.

## What a number cannot tell you

- Results on one Mac or one PC are a data point, not a population. Windows 10 and 11 are
  measured as separate platforms because the OS and the WebView2 runtime version differ.
- Unsigned builds downloaded through a browser carry a quarantine flag or Mark-of-the-Web.
  The harness copies from a local directory, so the first-run security checks of downloaded
  apps are not part of these numbers.
- Linux numbers produced in the development sandbox (Xvfb, no GPU) are smoke checks only and
  are not benchmark data.
