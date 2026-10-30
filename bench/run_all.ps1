# Windows: install the harness dependency into a private venv, then benchmark every built variant.
#   bench\run_all.ps1 [-Runs 10]     (a quiet machine is required, see docs\method.md)
# Reads dist\windows-x64\ (download the CI artifact first, or run scripts\build_all.ps1).
param([int]$Runs = 10)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Venv = Join-Path $Root '.venv-bench'
$Py = Join-Path $Venv 'Scripts\python.exe'
if (-not (Test-Path $Py)) { & python -m venv $Venv; if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' } }
& $Py -m pip install --quiet --disable-pip-version-check -r (Join-Path $Root 'bench\requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'pip install failed' }
$HostName = $env:COMPUTERNAME
$Out = Join-Path $Root ('results\' + $HostName + '-windows.json')
& $Py (Join-Path $Root 'bench\run.py') --variants all --runs $Runs --out $Out
exit $LASTEXITCODE
