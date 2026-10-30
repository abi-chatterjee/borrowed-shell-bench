# Borrowed Shell benchmark - build plan

## Goal

Produce the measurements for Section 7 of the paper "The Borrowed Shell Pattern":
download size, disk footprint, idle memory, cold start, install time/success,
and update cost, for one functionally identical app built with every strategy
the paper compares. Numbers must be reproducible by a third party from this repo.

The workspace this repo is built in is Linux-only. Real measurements happen on
the author's own machines (macOS Intel, macOS Apple Silicon, Windows 10,
Windows 11) by running one command per machine. Builds for macOS and Windows
happen in GitHub Actions. Nothing here may claim a platform was verified unless
it was actually run on that platform.

## Variants

| id | Strategy | Window | Backend transport | Notes |
|---|---|---|---|---|
| `electron` | Electron | bundled Chromium | Electron IPC (contextBridge preload) | electron-builder, unsigned zip per OS/arch |
| `tauri` | Tauri v2 | system web view | Tauri commands | unsigned bundle per OS/arch |
| `wails` | Wails v2 | system web view | Wails bindings | unsigned binary per OS/arch |
| `neutralino` | Neutralinojs | system web view | Neutralino extension or native API | zip per OS/arch |
| `pyinstaller` | PyInstaller + pywebview | system web view | loopback HTTP | frozen app per OS/arch (the "tried and replaced" baseline) |
| `bshell-py` | Borrowed Shell, Python | system web view via pywebview | loopback HTTP | pure wheel + install.sh / install.ps1 |
| `bshell-node` | Borrowed Shell, Node.js | system web view via a Node binding | loopback HTTP | npm tarball + install scripts; see risk R3 |

## The app ("Bench Notes")

Deliberately small and identical across variants:

- One page: a list of notes, a text editor, create / edit / delete, and a footer
  showing the variant id and version.
- Notes persist to a JSON file in a per-user data directory
  (`~/Library/Application Support/BenchNotes/<variant>` on macOS,
  `%LOCALAPPDATA%\BenchNotes\<variant>` on Windows, `~/.local/share/...` on Linux).
- Frontend: plain HTML/CSS/JS, no framework, no build step, under `frontend/`.
  Every variant ships these exact files. The only per-variant file is
  `frontend/api/<transport>.js`, a thin adapter exposing the same interface:
  `list()`, `save(note)`, `remove(id)`, `ready()`.
- Server-based variants (`pyinstaller`, `bshell-py`, `bshell-node`) bind to
  127.0.0.1 on a free port, check the `Host` header against that exact
  address and port, check `Origin`, and require a per-launch token passed to
  the window in the URL fragment and sent as a header. This is the hardening
  the paper recommends; implement it once per server language and test it.
- `ready()`: called once after the first render completes
  (`requestAnimationFrame` after DOMContentLoaded). The backend writes the
  current epoch milliseconds to the path in env var `BENCH_READY_FILE` if set.
  This is how the harness measures cold start without screen scraping.
- Env var `BENCH_DATA_DIR` overrides the data directory so runs are isolated.

## Borrowed Shell variants (follow the paper's Sections 4 and 5)

`bshell-py`:
- Package `benchnotes` (pure Python wheel). `python -m benchnotes ui` starts
  uvicorn (or the stdlib `http.server` if that keeps the wheel smaller; record
  the choice) on a second thread and pywebview on the main thread, waiting for
  the socket before opening the window. `python -m benchnotes ui --check` is
  the self-test: start server, fetch `/`, import the window backend, exit
  non-zero on failure. No silent browser fallback.
- On Windows, check the WebView2 and .NET 4.7.2 registry keys before importing
  pywebview's Windows backend, and print an actionable sentence if missing.
- `pythonw` has no stdout/stderr: redirect both to a log file first thing.
- `install.sh` (macOS/Linux) and `install.ps1` (Windows, ASCII-only,
  PowerShell 5.1 compatible, no double quotes in native-program arguments):
  everything inside `main()`; find Python 3.11+ or install one per user with
  uv (download uv's installer to a file first); create a private venv; pip
  install the wheel; build the shell; run `--check`; log to a file. All
  locations overridable by env vars (`BENCHNOTES_HOME`, `BENCHNOTES_APPS_DIR`,
  `BENCHNOTES_WHEEL` for a local wheel) so the harness can install into a
  scratch location.
- macOS shell: `Bench Notes (bshell-py).app` with Info.plist (own bundle id
  and name), `Contents/MacOS/launch` script that logs and execs a symlink to the
  real interpreter Mach-O (resolve through framework stubs), `pyvenv.cfg` and a
  `site-packages` symlink pointing at the venv. Build in a staging dir, run the
  self-test, then swap in.
- Windows shell: Start-menu `.lnk` targeting the venv's `pythonw.exe -m
  benchnotes ui`, with its own icon.
- Update path: `benchnotes update --wheel <path>` doing
  `pip install --no-index --upgrade`, falling back to an online install.

`bshell-node`: same structure with an npm package, a per-user Node.js if none
is found, and an equivalent shell. Pick the Node web view binding after
checking what exists and is maintained; record the decision and its trade-off
(see R3) in `docs/decisions.md`.

## Measurement harness (`bench/`)

Python 3.11+, depends only on `psutil`. One entry point per OS:
`bench/run_all.sh` (macOS) and `bench/run_all.ps1` (Windows), each calling
`python bench/run.py --variants all --runs 10 --out results/<host>.json`.

Per variant, per run:

1. **Install** from the artifacts in `dist/<os>-<arch>/` into a scratch
   location; record wall-clock install time and success (window opened and
   ready file written within 60 s).
2. **Download size**: bytes a new user would download. For packaged variants,
   the artifact size. For Borrowed Shell, sum of script + wheel/tarball, and
   separately the runtime download when no Python/Node is present (installer
   logs bytes fetched). Report both "runtime present" and "runtime absent".
3. **Disk footprint**: bytes on disk after install, first app (interpreter
   included) and marginal app (a second Borrowed Shell app sharing the
   interpreter) reported separately.
4. **Cold start**: launch the way a user would (`open` on the .app on macOS,
   the shortcut or exe on Windows), time from launch call to the epoch in the
   ready file. First launch after install and subsequent launches reported
   separately.
5. **Idle memory**: snapshot all processes before launch; 60 s after ready,
   sum RSS (and on macOS also physical footprint if obtainable) of every
   process that did not exist before. Process-tree walking is NOT enough:
   WKWebView content processes are XPC services parented to launchd, not to
   the app. Document the method and its noise in `docs/method.md`; require a
   quiet machine.
6. **Update cost** (Borrowed Shell and any variant with an update path):
   bytes and time to move from v1.0.0 to v1.0.1.
7. Quit the app and kill any leftover processes; verify none remain.

`bench/report.py` aggregates results files into median and IQR per metric per
platform and writes `results/summary.md` in the exact shape of the paper's
Table 7.5 plus one table per platform, and a CSV.

## CI (`.github/workflows/build.yml`)

Matrix: macOS arm64, macOS x64 (check which hosted runner labels are currently
available for Intel macOS and use that; if none, document it), Windows x64.
Each job builds every variant for that OS/arch, runs each variant's self-test or
smoke check headlessly where possible, and uploads `dist/<os>-<arch>/` as an
artifact. A `dist` job collects everything into one downloadable zip.
Note in the README that hosted Windows runners are Windows Server, so they build
but do not substitute for measuring on Windows 10 and 11.

## Repo layout

```
frontend/              shared UI + api/<transport>.js adapters
variants/<id>/         one folder per variant, each with build.sh/build.ps1
bshell/py/             wheel source, install.sh, install.ps1, shell builders
bshell/node/           npm package source, install scripts, shell builders
bench/                 run.py, report.py, run_all.sh, run_all.ps1, tests/
docs/method.md         measurement method and its known noise
docs/decisions.md      every non-obvious choice and its trade-off
docs/verification.md   what was run where, and what was not
.github/workflows/     build.yml
README.md              how to build, how to run on each machine, in that order
```

## What the agent must do in this Linux workspace

- Write all of the above.
- Build and run whatever runs on Linux, and say exactly what that was: the
  Python and Node servers with their Host/Origin/token checks (with tests), the
  wheel and npm builds, `install.sh` into a scratch dir up to the point a display
  is needed, the harness logic against a fake app that writes the ready file,
  `report.py` against synthetic results, the PowerShell scripts' static checks
  (ASCII, no double quotes in native args), and any variant builds whose Linux
  system libraries are installable here.
- Never mark a macOS or Windows path as verified. Record it in
  `docs/verification.md` as "written, not run".
- Do not push to any remote. Leave the repo as a local git repo with
  meaningful commits.

## Acceptance criteria

1. Every variant has source, a build script per OS, and a smoke check.
2. All seven variants share the same `frontend/` files except the adapter.
3. Server tests show a request with a wrong Host, foreign Origin, or missing
   token is refused.
4. Harness runs end to end on Linux against the fake app and produces
   `results/summary.md` from synthetic data in the paper's table shape.
5. CI workflow is syntactically valid (`actionlint` if installable).
6. `docs/verification.md` lists every component as run here, written not run,
   or not attempted, with reasons.
7. README gives a new person the exact commands, per machine, in order.

## Known risks (record outcomes in docs/decisions.md)

- R1: Tauri and Wails Linux builds need webkit2gtk development libraries that
  may not be installable here; if so, write the code and leave the build to CI.
- R2: Intel macOS hosted runners may be retired; the author may need to build
  the x64 macOS artifacts on his own Intel Mac via the same build scripts.
- R3: Node web view bindings are native addons, i.e. compiled code from npm.
  That re-introduces a binary the OS may evaluate (Smart App Control). This is
  a finding for the paper, not something to hide.
- R4: Idle memory on macOS is noisy and process attribution is imperfect;
  method and caveats must be explicit.
- R5: Fairness. Use each framework's default release configuration, no
  hand-tuning of one variant over another; record versions of every toolchain.

## Tech debt accepted up front

- One adapter file per transport duplicates a small amount of logic.
- The harness drives GUI launches through OS commands and polls files rather
  than instrumenting each framework, trading precision for uniformity.
- Hosted CI builds are not signed; that matches the paper's premise but means
  Gatekeeper/SmartScreen behaviour of browser-downloaded builds is out of scope.
