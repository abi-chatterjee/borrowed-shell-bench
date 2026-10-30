# Build the Neutralinojs variant on Windows: neu build with default settings, then a uniform zip.
. (Join-Path $PSScriptRoot '..\..\scripts\common.ps1')
$Stage = Join-Path $Build 'neutralino'
if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
if (Test-Path (Join-Path $Dist 'neutralino')) { Remove-Item -Recurse -Force (Join-Path $Dist 'neutralino') }
New-Item -ItemType Directory -Force -Path $Stage | Out-Null
foreach ($f in 'neutralino.config.json', 'package.json') { Copy-Item (Join-Path $Root ('variants\neutralino\' + $f)) $Stage }
Invoke-Checked $Python @((Join-Path $Root 'scripts\stage_frontend.py'), 'neutralino', (Join-Path $Stage 'resources'))
New-Item -ItemType Directory -Force -Path (Join-Path $Stage 'resources\icons') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Stage 'resources\js') | Out-Null
Copy-Item (Join-Path $Root 'assets\icons\icon.png') (Join-Path $Stage 'resources\icons\appIcon.png')
Invoke-Checked $Python @((Join-Path $Root 'scripts\render.py'), $Stage, $Version)
Push-Location $Stage
try {
    Invoke-Checked 'npm' @('install', '--no-audit', '--no-fund', '--no-progress')
    Copy-Item 'node_modules\@neutralinojs\lib\dist\neutralino.js' 'resources\js\neutralino.js'
    Invoke-Checked 'npx' @('neu', 'update')
    Invoke-Checked 'npx' @('neu', 'build')
}
finally { Pop-Location }
$Bin = 'benchnotes-neutralino-win_x64.exe'
$Pack = Join-Path $Build 'neutralino-pack'
if (Test-Path $Pack) { Remove-Item -Recurse -Force $Pack }
New-Item -ItemType Directory -Force -Path $Pack | Out-Null
Copy-Item (Join-Path $Stage ('dist\benchnotes-neutralino\' + $Bin)) $Pack
Copy-Item (Join-Path $Stage 'dist\benchnotes-neutralino\resources.neu') $Pack
$nodeV = (& node --version).Trim()
Complete-Zip 'neutralino' $Pack 'exe' $Bin @(('node=' + $nodeV), 'neutralinojs=6.10.0', 'neu-cli=11.8.0')
