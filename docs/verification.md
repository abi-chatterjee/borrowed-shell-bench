# Verification status

Three states only. "Run here" means it was executed in the Linux x86_64 development sandbox
(no real display; Xvfb where a window was needed) and the stated command gave the stated
result. "Written, not run" means the code exists and nothing has executed it. "Not attempted"
means it was not tried, with the reason.

Nothing in this repository has been run on macOS or Windows. Every macOS and Windows path
below is "written, not run", including the CI jobs. Expect the first real runs to find bugs.

Sandbox network: PyPI, npm, crates.io and GitHub were reachable; proxy.golang.org, nodejs.org
and docs.github.com were not (HTTP 403). No workaround was attempted.

## Run here

| Component | Command | Result |
|---|---|---|
| Python server: Host, Origin, token, path traversal, content type | `cd bshell/py && PYTHONPATH=src python3 -m unittest discover -s tests` | 30 tests, OK, 1 skipped (needs a venv with the wheel installed) |
| Node server: same checks | `cd bshell/node && npm test` | 19 tests, 19 pass; also on a clean `git archive` copy |
| Store behaviour (corrupt file, bad input, atomic write), Python and Node | same two commands | included in the counts above |
| macOS shell layout (the `.app` structure and `sys.prefix` resolution), built and self-tested on Linux | `test_shell_macos.py` in the Python suite | passes; this proves the layout logic, not that macOS runs the bundle |
| Shared frontend identical across variants | `python3 scripts/check_frontend.py --all` | all 7 variants, identical sha256 `994b22ac...c8b16` for non-adapter files |
| Python wheel (1.0.0 and 1.0.1) | `BENCH_VARIANTS=bshell-py BENCH_SKIP_SMOKE=1 sh scripts/build_all.sh` | wheels of 21 kB built |
| npm tarball (1.0.0 and 1.0.1) | `BENCH_VARIANTS=bshell-node BENCH_SKIP_SMOKE=1 sh scripts/build_all.sh` | tarballs of 15 kB built |
| `install.sh` (Python), end to end into a scratch home | `SMOKE_XVFB=1 SMOKE_SKIP_BACKEND=1 python3 variants/bshell-py/smoke.py` | OK. Used the Python already on the machine. `SKIP_BACKEND` skips the pywebview GTK import, which is not installed here |
| `install.sh` (Python), runtime provisioning branch | run with a fake uv installer served over `file://` (`bench/tests/fixtures/fake_uv_installer.sh`) | the branch executed and the log line parsed; a real `uv python install 3.12` was also run separately and downloaded and installed CPython 3.12.13 |
| `install.sh` (Node), end to end | `BENCHNOTES_NODE_DIST_URL=file://<fake dist> BENCHNOTES_FORCE_RUNTIME_INSTALL=1 SMOKE_XVFB=1 SMOKE_SKIP_BACKEND=1 python3 variants/bshell-node/smoke.py` | OK. nodejs.org is blocked, so the "official tarball + SHASUMS256" download path was run against a local stand-in built by `bench/tests/fixtures/make_fake_node_dist.py` with a real Node 24.22.1 binary and the real npm. The checksum logic ran; the real nodejs.org server was not contacted |
| Same Node smoke without the stand-in | `SMOKE_XVFB=1 SMOKE_SKIP_BACKEND=1 python3 variants/bshell-node/smoke.py` | FAILS here: no Node 24 on the machine, installer tries nodejs.org, 403. Expected given the sandbox |
| Update path, both languages | harness e2e plus manual runs of `benchnotes update` | 1.0.0 to 1.0.1 and version check pass on Linux |
| Node web view binding opens a real window | Node 24 + `benchnotes ui` under Xvfb | ready file written in about 0.5-1.1 s. Linux/WebKitGTK only |
| Electron | `sh variants/electron/build.sh` then `SMOKE_XVFB=1 python3 variants/electron/smoke.py` | built (125 MB zip); smoke OK (self-test); window opened under Xvfb, ready file written. Run as root with `--no-sandbox` |
| Tauri | `sh variants/tauri/build.sh`; `python3 variants/tauri/smoke.py`; `cargo test` in the rendered `build/linux-x64/tauri/src-tauri` | release build succeeded in 5m25s (2.9 MB zip); smoke OK; 2 Rust tests pass; window opened under Xvfb and wrote the ready file |
| Neutralino | `sh variants/neutralino/build.sh`; `python3 variants/neutralino/smoke.py` | built (1.1 MB zip); smoke is only a content check (binary + resources.neu, executable); window opened under Xvfb during development and wrote the ready file |
| PyInstaller | `sh variants/pyinstaller/build.sh`; `SMOKE_XVFB=1 python3 variants/pyinstaller/smoke.py` | built (14 MB zip); smoke OK. Frozen app's `ui --check` without `--skip-backend` fails on Linux with `No module named 'gi'` because the GTK backend is not bundled; Linux is not a benchmark platform |
| Wails store (Go) | `cd variants/wails && go test ./store/...` | pass |
| Harness logic end to end against a fake app | `python3 -m unittest discover -s bench/tests` (includes `test_run_e2e.py`) | 28 tests OK. Covers zip and installer variants, success and failure runs, a never-ready app (fails at the timeout, no stray processes), missing variants, smoke mode, report on harness output |
| Process attribution by snapshot difference, including an orphaned grandchild | `test_measure.py` | pass |
| `report.py` on synthetic data in Table 7.5 shape, per-platform tables, CSV | `python3 bench/tests/synthetic.py <dir>`; `python3 bench/report.py <dir>/*.json --out results/summary.md` | writes `results/summary.md` and `.csv`; SYNTHETIC banner; 7 rows per platform; `test_report.py` checks shape |
| PowerShell static checks: ASCII only, no BOM, no double quotes and no backticks in the installers, everything inside one function, no PowerShell 7 syntax, exit codes checked | `python3 -m unittest discover -s bench/tests -p test_install_ps1.py` | pass |
| PowerShell syntax parse of every `.ps1` | same test with `BENCH_PWSH=<path to pwsh 7.5.9>` | all parse. This is PowerShell 7.5.9 on Linux; it says nothing about PowerShell 5.1 behaviour |
| Shell script lint | `shellcheck -s sh $(git ls-files '*.sh')` | clean |
| CI workflow syntax | `actionlint .github/workflows/build.yml` (actionlint 1.7.12 from PyPI, shellcheck on) | no findings |
| Build orchestration | `sh scripts/build_all.sh` with `BENCH_VARIANTS` subsets | builds and prints a per-variant summary; exit code reflects failures |

## Written, not run

| Component | Why not run |
|---|---|
| Wails build and smoke (`variants/wails/build.*`, `smoke.py`, `main.go`, `app.go`) | The Wails CLI could not be installed: `go install` needs proxy.golang.org (403). Only the store tests ran. Likely to need a fix on first CI run |
| macOS builds of every variant | No macOS |
| macOS `.app` assembly and launch for bshell-py and bshell-node (`shell_macos`) | No macOS; only the Linux layout test ran |
| Windows builds of every variant (`build.ps1`, `common.ps1`, `py_wheel.ps1`) | No Windows |
| `install.ps1` for both Borrowed Shell packages, Windows shortcut creation, the Windows preflight (WebView2, .NET 4.7.2), `pythonw` log redirection, node `--detach` | No Windows; PowerShell 5.1 specifically has never been run. Static checks and a PowerShell 7 parse only |
| Windows and macOS paths of `bench/` (`open -n`, `launchctl setenv`, `footprint`, shortcut launch, `os.startfile`, `run_all.ps1`) | No macOS or Windows. The footprint parser is unit-tested on a sample string, not real output |
| macOS physical-footprint collection | Needs macOS |
| `.github/workflows/build.yml` job logic | Syntax checked by actionlint; no GitHub Actions run. Runner labels (`macos-15`, `macos-15-intel`, `windows-2025`) come from the GitHub changelog and web search, not from the runner reference page, which was unreachable. Action versions pinned in the file (`checkout@v4`, `setup-python@v5`, `setup-node@v4`, `setup-go@v5`, `upload-artifact@v4`, `download-artifact@v4`) were not verified against the marketplace |
| The Windows and macOS smoke checks in CI | Same as above; also on those hosts the Electron and Tauri smoke checks rely on their headless self-test modes, which ran on Linux only |
| Runtime-absent Python path with the real `astral.sh` installer | astral.sh was not part of the allowed network; `uv python install` itself was run, but not the installer script from astral.sh |
| Real nodejs.org download in the Node installers | nodejs.org blocked; stand-in used (see above) |
| Update cost with the online fallback | Not measured by design |

## Not attempted

| Component | Why |
|---|---|
| Any benchmark number from a real machine | Requires the author's macOS and Windows machines. The only numbers in this repository are synthetic and stamped as such |
| Real measurements on Linux | Linux is not a benchmark platform and the sandbox has no GPU or real display |
| Signing, notarization, Smart App Control or Gatekeeper behaviour on downloaded builds | Out of scope in the plan |
| Head-to-head test of alternative Node web view bindings | Only `@webviewjs/webview` was installed and run (decisions.md, R3) |
| Windows 10 vs 11 WebView2 version pinning | Not controllable from the repo |
