# Build the Electron variant on Windows: electron-builder --dir (default config, unsigned), then a uniform zip.
. (Join-Path $PSScriptRoot '..\..\scripts\common.ps1')
$Stage = Join-Path $Build 'electron'
if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
if (Test-Path (Join-Path $Dist 'electron')) { Remove-Item -Recurse -Force (Join-Path $Dist 'electron') }
New-Item -ItemType Directory -Force -Path $Stage | Out-Null
foreach ($f in 'package.json', 'main.js', 'preload.js') { Copy-Item (Join-Path $Root ('variants\electron\' + $f)) $Stage }
Copy-Item (Join-Path $Root 'bshell\node\src\store.js') (Join-Path $Stage 'store.js')
Invoke-Checked $Python @((Join-Path $Root 'scripts\stage_frontend.py'), 'electron', (Join-Path $Stage 'frontend'))
foreach ($f in 'icon.icns', 'icon.ico', 'icon.png') { Copy-Item (Join-Path $Root ('assets\icons\' + $f)) $Stage }
Invoke-Checked $Python @((Join-Path $Root 'scripts\render.py'), $Stage, $Version)
Push-Location $Stage
try {
    Invoke-Checked 'npm' @('install', '--no-audit', '--no-fund', '--no-progress')
    $env:CSC_IDENTITY_AUTO_DISCOVERY = 'false'
    Invoke-Checked 'npx' @('electron-builder', '--dir', '--publish', 'never')
}
finally { Pop-Location }
$Pack = Join-Path $Build 'electron-pack'
if (Test-Path $Pack) { Remove-Item -Recurse -Force $Pack }
New-Item -ItemType Directory -Force -Path $Pack | Out-Null
Copy-Item -Recurse -Force (Join-Path $Stage 'dist\win-unpacked\*') $Pack
$nodeV = (& node --version).Trim()
Complete-Zip 'electron' $Pack 'exe' 'Bench Notes (electron).exe' @(('node=' + $nodeV), 'electron=45.0.0', 'electron-builder=26.18.0')
