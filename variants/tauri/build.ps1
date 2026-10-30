# Build the Tauri v2 variant on Windows with tauri build defaults: bare executable, unsigned.
. (Join-Path $PSScriptRoot '..\..\scripts\common.ps1')
$Stage = Join-Path $Build 'tauri'
if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
if (Test-Path (Join-Path $Dist 'tauri')) { Remove-Item -Recurse -Force (Join-Path $Dist 'tauri') }
New-Item -ItemType Directory -Force -Path $Stage | Out-Null
Copy-Item (Join-Path $Root 'variants\tauri\package.json') $Stage
Copy-Item -Recurse (Join-Path $Root 'variants\tauri\src-tauri') (Join-Path $Stage 'src-tauri')
$icons = Join-Path $Stage 'src-tauri\icons'
New-Item -ItemType Directory -Force -Path $icons | Out-Null
foreach ($f in '32x32.png', '128x128.png', '128x128@2x.png', 'icon.icns', 'icon.ico', 'icon.png') { Copy-Item (Join-Path $Root ('assets\icons\' + $f)) $icons }
Invoke-Checked $Python @((Join-Path $Root 'scripts\stage_frontend.py'), 'tauri', (Join-Path $Stage 'frontend'))
Invoke-Checked $Python @((Join-Path $Root 'scripts\render.py'), $Stage, $Version)
Push-Location $Stage
try {
    Invoke-Checked 'npm' @('install', '--no-audit', '--no-fund', '--no-progress')
    Invoke-Checked 'npx' @('tauri', 'build', '--no-bundle')
}
finally { Pop-Location }
$Pack = Join-Path $Build 'tauri-pack'
if (Test-Path $Pack) { Remove-Item -Recurse -Force $Pack }
New-Item -ItemType Directory -Force -Path $Pack | Out-Null
Copy-Item (Join-Path $Stage 'src-tauri\target\release\benchnotes-tauri.exe') $Pack
$nodeV = (& node --version).Trim()
$rustV = ((& rustc --version).Split(' '))[1]
Complete-Zip 'tauri' $Pack 'exe' 'benchnotes-tauri.exe' @(('node=' + $nodeV), ('rust=' + $rustV), 'tauri-cli=2.12.4')
