# Build the bshell-py artifacts on Windows: wheel(s), install.ps1, manifest.
#   BENCH_VERSION (default 1.0.0), BENCH_UPDATE_VERSION (default 1.0.1)
. (Join-Path $PSScriptRoot '..\..\scripts\common.ps1')
. (Join-Path $PSScriptRoot '..\..\scripts\py_wheel.ps1')
$UpdateVersion = if ($env:BENCH_UPDATE_VERSION) { $env:BENCH_UPDATE_VERSION } else { '1.0.1' }
$Out = Join-Path $Dist 'bshell-py'
if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Build-PyWheel $Version $Out
Build-PyWheel $UpdateVersion $Out
Copy-Item (Join-Path $Root 'bshell\py\install.sh') $Out
Copy-Item (Join-Path $Root 'bshell\py\install.ps1') $Out
$wheel = 'benchnotes-' + $Version + '-py3-none-any.whl'
Invoke-Checked $Python @((Join-Path $Root 'scripts\check_frontend.py'), '--archive', (Join-Path $Out $wheel), 'http')
$pyV = (& $Python -c 'import sys;print(sys.version.split()[0])').Trim()
Invoke-Checked $Python @((Join-Path $Root 'scripts\write_manifest.py'), '--dir', $Out, '--variant', 'bshell-py', '--version', $Version,
    '--kind', 'installer', '--installer', 'install.ps1', '--artifact', 'install.ps1', '--artifact', $wheel,
    '--update-artifact', ('benchnotes-' + $UpdateVersion + '-py3-none-any.whl'),
    '--tool', ('python=' + $pyV), '--tool', 'pywebview=6.2.1', '--tool', 'hatchling=1.32.4')
Write-Host ('bshell-py built in ' + $Out)
