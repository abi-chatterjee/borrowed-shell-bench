# Borrowed Shell benchmark

One small app, "Bench Notes" (a list of notes, an editor, create / edit / delete), built seven
ways, plus a harness that measures each build the way a user would meet it. It produces the
numbers for Section 7 of the paper "The Borrowed Shell Pattern": download size, disk
footprint, idle memory, cold start, install time and success, and update cost.

| id | Strategy | Window | Backend transport |
|---|---|---|---|
| `electron` | Electron | bundled Chromium | Electron IPC (contextBridge preload) |
| `tauri` | Tauri v2 | system web view | Tauri commands |
| `wails` | Wails v2 | system web view | Wails bindings |
| `neutralino` | Neutralinojs | system web view | Neutralino native API (filesystem) |
| `pyinstaller` | PyInstaller + pywebview | system web view | loopback HTTP |
| `bshell-py` | Borrowed Shell, Python wheel | system web view via pywebview | loopback HTTP |
| `bshell-node` | Borrowed Shell, Node.js package | system web view via a Node native addon | loopback HTTP |

Read these before trusting a number: [docs/method.md](docs/method.md) (how each metric is
measured and how noisy it is), [docs/decisions.md](docs/decisions.md) (every non-obvious
choice, the outcome of each known risk), [docs/verification.md](docs/verification.md) (what
was actually run, where, and what was not).

Status in one paragraph: the code was written and tested in a Linux sandbox with no display
server of its own. The macOS and Windows paths (the `.app` builder, the Windows shortcut
builder, the PowerShell installers, the macOS and Windows launch and memory code in the
harness, the CI jobs) have not been run on those systems. The first real run on each
machine will find bugs; docs/verification.md lists exactly what to expect to be unproven.

## Repository layout

```
frontend/              shared UI + api/<transport>.js adapters (the only per-variant file)
variants/<id>/         one folder per variant: build.sh, build.ps1, smoke.py, sources
bshell/py/             wheel source, install.sh, install.ps1, macOS/Windows shell builders
bshell/node/           npm package source, install.sh, install.ps1, shell builders
scripts/               build helpers, build_all.sh / build_all.ps1
bench/                 run.py, report.py, run_all.sh, run_all.ps1, tests/
docs/                  method, decisions, verification
.github/workflows/     build.yml
```

## 1. Build

Builds are per OS and architecture. You need the artifacts for each machine you will
measure: `dist/macos-arm64/`, `dist/macos-x64/`, `dist/windows-x64/`.

### Option A: GitHub Actions (default)

Push the repository to a GitHub repository you control, run the `build` workflow (it also
runs on every push to `main` and on pull requests), then download the artifact
`borrowed-shell-bench-dist` from the run. Unzip it into the repository root so that you have
`dist/macos-arm64/`, `dist/macos-x64/`, `dist/windows-x64/`.

Things to know:

- Intel macOS uses the label `macos-15-intel`. GitHub has announced that Intel macOS hosted
  runners end when the macOS 15 image is retired (fall 2027). If the label stops resolving,
  build on an Intel Mac with option B; the scripts are identical.
- Hosted Windows runners are Windows Server. They build and smoke-test, but they do not
  substitute for measuring on Windows 10 and Windows 11.
- Builds are unsigned on purpose.

### Option B: build locally on the machine you will measure

Prerequisites (versions used and pinned by the scripts are in docs/decisions.md):
Python 3.11+ (3.13 recommended), Node.js 24, Go 1.24, Rust stable, and the Wails CLI
(`go install github.com/wailsapp/wails/v2/cmd/wails@v2.17.0`). On macOS also the Xcode
command line tools. On Windows also WebView2 (present on Windows 11 and current Windows 10).

macOS:

```sh
git clone <your repository> && cd borrowed-shell-bench
sh scripts/build_all.sh                  # builds every variant, then runs each smoke check
```

Windows (PowerShell):

```powershell
git clone <your repository>; cd borrowed-shell-bench
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_all.ps1
```

Useful switches: `BENCH_VARIANTS="tauri bshell-py"` builds a subset, `BENCH_SKIP_SMOKE=1`
skips the smoke checks, `BENCH_VERSION` changes the app version (default 1.0.0; the Borrowed
Shell builds also produce 1.0.1 packages for the update measurement). Output lands in
`dist/<os>-<arch>/<variant>/` with a `manifest.json` per variant. Intermediate files go to
`build/`.

## 2. Measure, on each machine, in this order

Do this on each of: macOS Intel, macOS Apple Silicon, Windows 10, Windows 11. Each run needs
network access (the "runtime absent" pass downloads Python or Node, and the Borrowed Shell
installers fetch packages).

Before you start: restart the machine, close everything else, disable sleep, leave it
plugged in, and do not touch it during the run. The harness refuses to start if total CPU is
busy (override with `--no-quiet-check`, and expect noisy results).

1. Get the repository and the matching `dist/<os>-<arch>/` onto the machine (option A
   download, or option B build).
2. Run the harness. About 10 runs x 7 variants x (about 1.5 minutes of idle wait per run);
   plan on a couple of hours.

   macOS:
   ```sh
   bench/run_all.sh 10                    # writes results/<host>-<arch>.json
   ```
   Windows:
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File bench\run_all.ps1 -Runs 10   # writes results\<host>-windows.json
   ```
   Both create a private venv `.venv-bench` and install only `psutil`.
3. Copy the `results/*.json` files from every machine into one `results/` folder.

## 3. Report (any machine)

```sh
python -m venv .venv-bench && .venv-bench/bin/pip install -r bench/requirements.txt
.venv-bench/bin/python bench/report.py results/*.json --out results/summary.md
```

(on Windows use `.venv-bench\Scripts\python.exe` and `pip.exe`). This writes
`results/summary.md` (a Table 7.5 style summary plus one table per platform: medians with the
interquartile range) and `results/summary.csv` (every metric, long format). Use
`--table75-platform "macOS arm64"` to restrict the summary table to one platform; pooling
operating systems mixes different web views and is not recommended for claims.

The shape of Table 7.5 in `report.py` is an assumption (rows are variants, columns follow the
metric list of the plan), because the paper text is not in this repository. Edit `TABLE_75`
at the top of `bench/report.py` to match the paper.

To see the report on made-up data: `python bench/tests/synthetic.py /tmp/syn` then
`python bench/report.py /tmp/syn/*.json --out results/summary.md`. The output is stamped
SYNTHETIC.

## Tests that run on any machine

```sh
python -m unittest discover -s bench/tests                      # harness, report, PowerShell static checks
(cd bshell/py && PYTHONPATH=src python -m unittest discover -s tests)   # Python server and store
(cd bshell/node && npm test)                                    # Node server and store
(cd variants/wails && go test ./store/...)                      # Wails store
python scripts/check_frontend.py --all                          # identical frontend in all variants
```

`pwsh` is optional: when present, `bench/tests/test_install_ps1.py` also parses every `.ps1`
with the PowerShell parser (a PowerShell 7 parser, so a syntax check only, not a PowerShell
5.1 test).

## Using the Borrowed Shell packages directly

`bshell/py/install.sh` / `install.ps1` and `bshell/node/install.sh` / `install.ps1` are the
installers a user would run. They are configured with environment variables
(`BENCHNOTES_HOME`, `BENCHNOTES_APPS_DIR`, `BENCHNOTES_WHEEL` or `BENCHNOTES_TARBALL`,
`BENCHNOTES_FORCE_RUNTIME_INSTALL`, ...; each script lists them at the top), which is how the
harness installs into a scratch location. Both build a native shell: a `.app` bundle on
macOS, a Start-menu shortcut on Windows.
